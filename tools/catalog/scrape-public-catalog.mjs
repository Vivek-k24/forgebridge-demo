#!/usr/bin/env node

/**
 * PartGraph public catalog candidate collector.
 *
 * Purpose:
 * - collect factual Honda OEM-number/name/quantity observations from an explicit source manifest
 * - preserve provenance
 * - never infer mechanical relationships, repair procedures, torque, fluids, safety facts, or interchange
 *
 * This is an internal research/ingestion tool. It intentionally writes CANDIDATES only.
 */

import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import process from 'node:process';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const SOURCES_PATH = resolve(ROOT, 'tools/catalog/sources.json');
const OUTPUT_PATH = resolve(ROOT, 'data/catalog/part-candidates.json');
const USER_AGENT = 'PartGraphCatalogResearch/0.1 (+https://github.com/Vivek-k24/forgebridge-demo)';
const MIN_DELAY_MS = 1200;
const PART_NUMBER_RE = /\b([0-9A-Z]{5}-[0-9A-Z]{3}-[0-9A-Z]{3})\b/g;

function argValue(name) {
  const prefix = `${name}=`;
  const item = process.argv.find((value) => value.startsWith(prefix));
  return item ? item.slice(prefix.length) : undefined;
}

const limitArg = Number.parseInt(argValue('--limit') ?? '', 10);
const sourceLimit = Number.isFinite(limitArg) && limitArg > 0 ? limitArg : Infinity;
const domainArg = argValue('--domain');

function sleep(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

function decodeEntities(value) {
  return value
    .replaceAll('&nbsp;', ' ')
    .replaceAll('&amp;', '&')
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
}

function htmlToLines(html) {
  const withoutNoise = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<(?:br|\/p|\/div|\/li|\/tr|\/td|\/h[1-6])\b[^>]*>/gi, '\n')
    .replace(/<[^>]+>/g, ' ');

  return decodeEntities(withoutNoise)
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
}

function looksLikeNoise(line) {
  return (
    /^\$\d/.test(line) ||
    /^(add to cart|view details|view|price|msrp|sort by|ref no\.?|part no\.?|change vehicle)$/i.test(line) ||
    /^(package quantity|require quantity)\s*:/i.test(line) ||
    /^\d+$/.test(line)
  );
}

function inferName(lines, index, partNumber) {
  const sameLine = lines[index];
  const afterNumber = sameLine.slice(sameLine.indexOf(partNumber) + partNumber.length).trim();
  if (afterNumber && !looksLikeNoise(afterNumber)) return afterNumber.slice(0, 160);

  for (let offset = 1; offset <= 5; offset += 1) {
    const candidate = lines[index + offset];
    if (!candidate || looksLikeNoise(candidate) || PART_NUMBER_RE.test(candidate)) {
      PART_NUMBER_RE.lastIndex = 0;
      continue;
    }
    PART_NUMBER_RE.lastIndex = 0;
    return candidate.slice(0, 160);
  }
  return undefined;
}

function inferQuantity(lines, index) {
  for (let offset = 0; offset <= 8; offset += 1) {
    const candidate = lines[index + offset] ?? '';
    const match = candidate.match(/Require Quantity\s*:\s*(\d+)/i) ?? candidate.match(/\bQty(?:uantity)?\s*[:x]?\s*(\d+)\b/i);
    if (match) return Number.parseInt(match[1], 10);
  }
  return undefined;
}

function extractPartCandidates(html, source) {
  const lines = htmlToLines(html);
  const observations = [];
  const seen = new Set();

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    PART_NUMBER_RE.lastIndex = 0;
    const matches = [...line.matchAll(PART_NUMBER_RE)];
    for (const match of matches) {
      const oemNumber = match[1].toUpperCase();
      if (seen.has(oemNumber)) continue;
      seen.add(oemNumber);

      observations.push({
        oemNumber,
        observedName: inferName(lines, index, oemNumber),
        observedQuantity: inferQuantity(lines, index),
        vehicleConfigId: source.vehicleConfigId,
        sourceId: source.id,
        sourceUrl: source.url,
        sourceType: source.sourceType,
        trustUse: source.trustUse,
        reviewStatus: 'candidate',
        evidenceText: lines.slice(Math.max(0, index - 1), Math.min(lines.length, index + 6)).join(' | ').slice(0, 700),
      });
    }
  }

  return observations;
}

function robotsRulesForUserAgent(text) {
  const lines = text.split(/\r?\n/).map((line) => line.replace(/#.*$/, '').trim()).filter(Boolean);
  let applies = false;
  const disallow = [];

  for (const line of lines) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim().toLowerCase();
    const value = line.slice(separator + 1).trim();

    if (key === 'user-agent') {
      applies = value === '*';
      continue;
    }
    if (applies && key === 'disallow' && value) disallow.push(value);
  }
  return disallow;
}

async function robotsAllows(url) {
  const target = new URL(url);
  const robotsUrl = `${target.origin}/robots.txt`;
  try {
    const response = await fetch(robotsUrl, {headers: {'User-Agent': USER_AGENT, Accept: 'text/plain'}});
    if (!response.ok) return {allowed: true, reason: `robots.txt unavailable (${response.status}); no automated denial observed`};
    const disallow = robotsRulesForUserAgent(await response.text());
    const blockedBy = disallow.find((path) => target.pathname.startsWith(path));
    return blockedBy
      ? {allowed: false, reason: `robots.txt disallows ${blockedBy}`}
      : {allowed: true, reason: 'robots.txt permits this path for User-agent: *'};
  } catch (error) {
    return {allowed: false, reason: `robots.txt check failed: ${error instanceof Error ? error.message : String(error)}`};
  }
}

async function fetchHtml(source) {
  const response = await fetch(source.url, {
    redirect: 'follow',
    headers: {
      'User-Agent': USER_AGENT,
      Accept: 'text/html,application/xhtml+xml',
    },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('text/html')) throw new Error(`Unexpected content type: ${contentType || 'unknown'}`);
  return response.text();
}

async function main() {
  const sources = JSON.parse(await readFile(SOURCES_PATH, 'utf8'));
  const selected = sources
    .filter((source) => source.enabled)
    .filter((source) => !domainArg || source.domain === domainArg)
    .slice(0, sourceLimit);

  const result = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    policy: {
      outputStatus: 'candidate-only',
      storesRawHtml: false,
      downloadsImages: false,
      infersMechanicalFacts: false,
      note: 'A catalog observation may support part identity/fitment review. It never becomes repair truth automatically.',
    },
    runs: [],
    candidates: [],
  };

  for (const source of selected) {
    const startedAt = new Date().toISOString();
    const robots = await robotsAllows(source.url);
    const run = {
      sourceId: source.id,
      sourceUrl: source.url,
      startedAt,
      finishedAt: null,
      robotsAllowed: robots.allowed,
      robotsReason: robots.reason,
      extractedPartCount: 0,
      error: null,
    };

    if (!robots.allowed) {
      run.error = 'Skipped: robots policy did not permit automated collection.';
      run.finishedAt = new Date().toISOString();
      result.runs.push(run);
      continue;
    }

    try {
      const html = await fetchHtml(source);
      const observations = extractPartCandidates(html, source);
      run.extractedPartCount = observations.length;
      result.candidates.push(...observations);
    } catch (error) {
      run.error = error instanceof Error ? error.message : String(error);
    }

    run.finishedAt = new Date().toISOString();
    result.runs.push(run);
    await sleep(MIN_DELAY_MS);
  }

  result.candidates.sort((a, b) => a.oemNumber.localeCompare(b.oemNumber) || a.sourceId.localeCompare(b.sourceId));
  await mkdir(dirname(OUTPUT_PATH), {recursive: true});
  await writeFile(OUTPUT_PATH, `${JSON.stringify(result, null, 2)}\n`, 'utf8');

  const successful = result.runs.filter((run) => !run.error).length;
  const blocked = result.runs.filter((run) => !run.robotsAllowed).length;
  console.log(`PartGraph catalog collector: ${successful}/${result.runs.length} sources fetched, ${blocked} robots-blocked, ${result.candidates.length} candidate observations.`);
  console.log(`Wrote ${OUTPUT_PATH}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
