#!/usr/bin/env node

/**
 * Structural + human approval gate for a Honda ServiceExpress candidate file.
 * This does not manufacture verification. It checks the file, requires an
 * explicit reviewer, and writes an immutable reviewed snapshot for downstream
 * graph authoring.
 *
 * Usage:
 *   node tools/catalog/review-honda-oem-candidate.mjs \
 *     --input catalog/generated/...oem-candidate.json \
 *     --reviewer "VK" \
 *     --decision approve
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

const args = process.argv.slice(2);
const arg = (name) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
};
const required = (name) => {
  const value = arg(name);
  if (!value) throw new Error(`Missing required ${name}`);
  return value;
};

const inputPath = required('--input');
const reviewer = required('--reviewer').trim();
const decision = required('--decision').toLowerCase();
const outputDir = arg('--output-dir') ?? 'catalog/reviewed';

if (!['approve', 'reject'].includes(decision)) throw new Error('--decision must be approve or reject');
if (!reviewer) throw new Error('Reviewer cannot be blank');

const raw = await fs.readFile(inputPath, 'utf8');
const candidate = JSON.parse(raw);

if (candidate.kind !== 'honda-service-express-oem-candidate') throw new Error('Input is not a Honda ServiceExpress OEM candidate file.');
if (candidate.source?.type !== 'honda-official') throw new Error('Candidate does not identify an official Honda source.');
if (!candidate.vehicleConfigId || !candidate.sectionId) throw new Error('Candidate is missing vehicleConfigId or sectionId.');
if (!Array.isArray(candidate.parts) || !candidate.parts.length) throw new Error('Candidate contains no parts.');

const badNumbers = candidate.parts.filter((part) => !/^\d{5}-[A-Z0-9]{3}-[A-Z0-9]{2,5}$/.test(String(part.oemNumber ?? '')));
if (badNumbers.length) throw new Error(`Candidate contains ${badNumbers.length} malformed Honda part number(s).`);

const duplicateNumbers = candidate.parts
  .map((part) => part.oemNumber)
  .filter((number, index, all) => all.indexOf(number) !== index);
if (duplicateNumbers.length) throw new Error(`Duplicate OEM numbers: ${[...new Set(duplicateNumbers)].join(', ')}`);

const reviewedAt = new Date().toISOString();
const inputSha256 = crypto.createHash('sha256').update(raw).digest('hex');
const reviewed = {
  ...candidate,
  kind: 'honda-service-express-oem-reviewed',
  review: {
    decision,
    reviewer,
    reviewedAt,
    inputSha256,
    note: decision === 'approve'
      ? 'Approved as OEM part-identity/fitment evidence for this exact vehicle/section. Mechanical relationships and service procedures remain separate facts requiring their own sources.'
      : 'Rejected; do not publish into PartGraph coverage.',
  },
  trustBoundary: {
    ...candidate.trustBoundary,
    partIdentityCandidate: decision !== 'approve',
    fitmentCandidate: decision !== 'approve',
    partIdentityVerified: decision === 'approve',
    fitmentVerified: decision === 'approve',
    mechanicalRelationshipVerified: false,
    serviceProcedureVerified: false,
  },
};

await fs.mkdir(outputDir, {recursive: true});
const suffix = decision === 'approve' ? 'oem-reviewed' : 'oem-rejected';
const outputPath = path.join(outputDir, `${candidate.vehicleConfigId}.${candidate.sectionId}.${suffix}.json`);
await fs.writeFile(outputPath, `${JSON.stringify(reviewed, null, 2)}\n`, 'utf8');
console.log(`${decision.toUpperCase()}: ${outputPath}`);
console.log(`Parts: ${candidate.parts.length}`);
console.log('This approval covers OEM identity/fitment evidence only; it does not verify repair mechanics.');
