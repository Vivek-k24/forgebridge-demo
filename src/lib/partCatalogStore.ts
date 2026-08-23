import {demoVehicle, type PartNode, type SourceClaim} from '../data/partGraphDemo';
import {publishedRepairGraphs} from '../data/partGraphSystems';

export type CatalogReviewStatus = 'candidate' | 'corroborated' | 'verified' | 'rejected';

export interface CatalogVehicleRecord {
  id: string;
  make: string;
  year: number;
  model: string;
  trim: string;
  body: string;
  engine: string;
  transmission: string;
  market: string;
}

export interface CatalogPartRecord {
  oemNumber: string;
  canonicalName: string;
  supersededNumbers: string[];
  graphIds: string[];
  sourceUrls: string[];
  sourceLabels: string[];
  status: CatalogReviewStatus;
}

export interface CatalogFitmentRecord {
  vehicleConfigId: string;
  oemNumber: string;
  graphId: string;
  partId: string;
  observedName: string;
  quantity: number;
  source: SourceClaim;
  status: CatalogReviewStatus;
}

function normalizeOemNumber(value: string) {
  return value.trim().toUpperCase();
}

function verifiedStatus(part: PartNode): CatalogReviewStatus {
  return part.source.status === 'verified' && part.oemNumber ? 'verified' : 'candidate';
}

export function currentCatalogVehicle(): CatalogVehicleRecord {
  return {
    id: demoVehicle.id,
    make: demoVehicle.make,
    year: demoVehicle.year,
    model: demoVehicle.model,
    trim: demoVehicle.trim,
    body: demoVehicle.body,
    engine: demoVehicle.engine,
    transmission: demoVehicle.transmission,
    market: demoVehicle.market,
  };
}

export function listStaticCatalogFitments(): CatalogFitmentRecord[] {
  const records: CatalogFitmentRecord[] = [];

  for (const graph of publishedRepairGraphs) {
    for (const part of graph.parts) {
      if (!part.oemNumber) continue;
      records.push({
        vehicleConfigId: demoVehicle.id,
        oemNumber: normalizeOemNumber(part.oemNumber),
        graphId: graph.id,
        partId: part.id,
        observedName: part.name,
        quantity: part.quantity,
        source: part.source,
        status: verifiedStatus(part),
      });
    }
  }

  return records.sort((a, b) => a.oemNumber.localeCompare(b.oemNumber) || a.graphId.localeCompare(b.graphId));
}

export function listStaticCatalogParts(): CatalogPartRecord[] {
  const byOem = new Map<string, CatalogPartRecord>();

  for (const graph of publishedRepairGraphs) {
    for (const part of graph.parts) {
      if (!part.oemNumber) continue;
      const oemNumber = normalizeOemNumber(part.oemNumber);
      const existing = byOem.get(oemNumber);
      const sourceUrl = part.source.url;

      if (existing) {
        if (!existing.graphIds.includes(graph.id)) existing.graphIds.push(graph.id);
        if (sourceUrl && !existing.sourceUrls.includes(sourceUrl)) existing.sourceUrls.push(sourceUrl);
        if (!existing.sourceLabels.includes(part.source.label)) existing.sourceLabels.push(part.source.label);
        for (const superseded of part.supersededNumbers ?? []) {
          const normalized = normalizeOemNumber(superseded);
          if (!existing.supersededNumbers.includes(normalized)) existing.supersededNumbers.push(normalized);
        }
        if (verifiedStatus(part) === 'verified') existing.status = 'verified';
        continue;
      }

      byOem.set(oemNumber, {
        oemNumber,
        canonicalName: part.name,
        supersededNumbers: (part.supersededNumbers ?? []).map(normalizeOemNumber),
        graphIds: [graph.id],
        sourceUrls: sourceUrl ? [sourceUrl] : [],
        sourceLabels: [part.source.label],
        status: verifiedStatus(part),
      });
    }
  }

  return [...byOem.values()].sort((a, b) => a.oemNumber.localeCompare(b.oemNumber));
}

export function findStaticCatalogPart(oemNumber: string): CatalogPartRecord | undefined {
  const normalized = normalizeOemNumber(oemNumber);
  return listStaticCatalogParts().find((part) => part.oemNumber === normalized || part.supersededNumbers.includes(normalized));
}

export function fitmentsForOemNumber(oemNumber: string): CatalogFitmentRecord[] {
  const normalized = normalizeOemNumber(oemNumber);
  return listStaticCatalogFitments().filter((record) => record.oemNumber === normalized);
}
