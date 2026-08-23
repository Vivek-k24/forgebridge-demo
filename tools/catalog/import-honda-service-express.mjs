#!/usr/bin/env node

/**
 * PartGraph Honda OEM importer
 *
 * Purpose:
 *   Convert a legally obtained/saved American Honda ServiceExpress Parts Info
 *   snapshot into a small structured candidate file that can be reviewed and
 *   published into PartGraph.
 *
 * Important:
 *   - This script does NOT log in to Honda, bypass authentication, or scrape a
 *     subscription session.
 *   - It uses zero LLM/model tokens.
 *   - It does not infer repair procedure, torque, fluids, pressure, metallurgy,
 *     interchange, or part-to-part mechanical relationships.
 *   - A human review step is still required before a candidate becomes
 *     PartGraph mechanical truth.
 *
 * Accepted input:
 *   1) JSON export/snapshot in the schema documented in OEM_PIPELINE.md, or
 *   2) saved text/HTML copied from a ServiceExpress Parts Info result page.
 *
 * Usage:
 *   node tools/catalog/import-honda-service-express.mjs \
 *     --input ./private/honda-radiator.html \
 *     --vehicle honda-civic-2009-hybrid-us \
 *     --section radiator-denso \
 *     --source-url "https://techinfo.honda.com/..."
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

const args = process.argv.slice(2);

function arg(name) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
}

function required(name) {
  const value = arg(name);
  if (!value) throw new Error(`Missing required ${name}`);
  return value;
}

function stripHtml(value) {
  return value
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizePartNumber(value) {
  return value.toUpperCase().replace(/[^A-Z0-9-]/g, '').trim();
}

function looksLikeHondaPartNumber(value) {
  return /^\d{5}-[A-Z0-9]{3}-[A-Z0-9]{3,5}$/.test(value)
    || /^\d{5}-[A-Z0-9]{3}-\d{3,5}$/.test(value)
    || /^\d{5}-\d{5}-[A-Z0-9]{2}$/.test(value);
}

function nearbyName(text, start, end) {
  const before = text.slice(Math.max(0, start - 120), start);
  const after = text.slice(end, Math.min(text.length, end + 180));
  const neighborhood = `${before} ${after}`
    .replace(/\b(?:MSRP|PRICE|QTY|QUANTITY|PART|NUMBER|HONDA|GENUINE)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const words = neighborhood.split(' ').filter(Boolean);
  return words.slice(Math.max(0, words.length - 14)).join(' ').slice(0, 180);
}

function extractFromText(raw) {
  const text = stripHtml(raw);
  const regex = /\b\d{5}-[A-Z0-9]{3}-[A-Z0-9]{2,5}\b/gi;
  const found = new Map();
  for (const match of text.matchAll(regex)) {
    const oemNumber = normalizePartNumber(match[0]);
    if (!looksLikeHondaPartNumber(oemNumber) || found.has(oemNumber)) continue;
    found.set(oemNumber, {
      oemNumber,
      observedName: nearbyName(text, match.index ?? 0, (match.index ?? 0) + match[0].length),
      observedQuantity: null,
      callout: null,
    });
  }
  return [...found.values()];
}

function extractFromJson(parsed) {
  const rows = [];
  const illustrations = Array.isArray(parsed.illustrations) ? parsed.illustrations : [];
  for (const illustration of illustrations) {
    const parts = Array.isArray(illustration.parts) ? illustration.parts : [];
    for (const item of parts) {
      const oemNumber = normalizePartNumber(String(item.partNumber ?? item.oemNumber ?? ''));
      if (!looksLikeHondaPartNumber(oemNumber)) continue;
      rows.push({
        oemNumber,
        observedName: String(item.name ?? item.description ?? '').trim() || null,
        observedQuantity: Number.isFinite(Number(item.quantity)) ? Number(item.quantity) : null,
        callout: item.callout == null ? null : String(item.callout),
        illustration: String(illustration.name ?? illustration.illustration ?? '').trim() || null,
        section: String(illustration.section ?? '').trim() || null,
      });
    }
  }
  return rows;
}

function dedupe(rows) {
  const map = new Map();
  for (const row of rows) {
    const existing = map.get(row.oemNumber);
    if (!existing) {
      map.set(row.oemNumber, row);
      continue;
    }
    map.set(row.oemNumber, {
      ...existing,
      observedName: existing.observedName || row.observedName,
      observedQuantity: existing.observedQuantity ?? row.observedQuantity,
      callout: existing.callout ?? row.callout,
      illustration: existing.illustration ?? row.illustration,
      section: existing.section ?? row.section,
    });
  }
  return [...map.values()].sort((a, b) => a.oemNumber.localeCompare(b.oemNumber));
}

const inputPath = required('--input');
const vehicleConfigId = required('--vehicle');
const sectionId = required('--section');
const sourceUrl = required('--source-url');
const outputDir = arg('--output-dir') ?? 'catalog/generated';

const raw = await fs.readFile(inputPath, 'utf8');
let rows;
let sourceMetadata = {};
try {
  const parsed = JSON.parse(raw);
  rows = extractFromJson(parsed);
  sourceMetadata = parsed.source && typeof parsed.source === 'object' ? parsed.source : {};
} catch {
  rows = extractFromText(raw);
}

const parts = dedupe(rows);
if (!parts.length) throw new Error('No Honda-style OEM part numbers were found. Nothing was written.');

const capturedAt = String(sourceMetadata.capturedAt ?? new Date().toISOString());
const sourceHash = crypto.createHash('sha256').update(raw).digest('hex');
const output = {
  schemaVersion: 1,
  kind: 'honda-service-express-oem-candidate',
  vehicleConfigId,
  sectionId,
  source: {
    type: 'honda-official',
    label: 'American Honda ServiceExpress Parts Info',
    url: sourceUrl,
    capturedAt,
    sha256: sourceHash,
    inputFile: path.basename(inputPath),
  },
  trustBoundary: {
    partIdentityCandidate: true,
    fitmentCandidate: true,
    mechanicalRelationshipVerified: false,
    serviceProcedureVerified: false,
    shoppingVerified: false,
  },
  parts,
};

await fs.mkdir(outputDir, {recursive: true});
const outputPath = path.join(outputDir, `${vehicleConfigId}.${sectionId}.oem-candidate.json`);
await fs.writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
console.log(`Wrote ${parts.length} OEM candidate parts to ${outputPath}`);
console.log(`Source SHA-256: ${sourceHash}`);
console.log('Next: run review-honda-oem-candidate.mjs with an explicit reviewer and decision file.');
