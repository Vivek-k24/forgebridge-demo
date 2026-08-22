import type {PartNode, PartRelation, PartState} from '../data/partGraphDemo';

export interface RepairLine {
  part: PartNode;
  state: PartState;
  included: boolean;
  reason: string;
}

export function questionForPart(part: PartNode): string {
  if (part.requirement === 'adjacent-only') return `Is the ${part.name} damaged or worth inspecting while this area is open?`;
  if (part.requirement === 'inspect') return `Do you already have a usable ${part.name}, or does it need inspection?`;
  if (part.requirement === 'normally-reusable') return `Can the existing ${part.name} be reused?`;
  if (part.requirement === 'single-use') return `Has the ${part.name} been disturbed or removed?`;
  return `Do you need the ${part.name}?`;
}

export function buildRepairLines(parts: PartNode[], states: Record<string, PartState>): RepairLine[] {
  return parts.map((part) => {
    const state = states[part.id] ?? 'not-sure';
    const included = state === 'need';
    const reason = state === 'need'
      ? 'Add to repair package'
      : state === 'have'
        ? 'User says this part is already available'
        : state === 'inspect'
          ? 'Inspect before purchase'
          : 'User has not confirmed this item yet';
    return {part, state, included, reason};
  });
}

export function connectedPartIds(targetId: string, relations: PartRelation[]): Set<string> {
  const ids = new Set<string>([targetId]);
  for (const relation of relations) {
    if (relation.from === targetId) ids.add(relation.to);
    if (relation.to === targetId) ids.add(relation.from);
  }
  return ids;
}

export function completenessScore(lines: RepairLine[]): number {
  const resolved = lines.filter((line) => line.state !== 'not-sure').length;
  return Math.round((resolved / Math.max(lines.length, 1)) * 100);
}

export function validateGraph(parts: PartNode[], relations: PartRelation[]): string[] {
  const errors: string[] = [];
  const partIds = new Set(parts.map((part) => part.id));

  for (const part of parts) {
    if (part.quantity < 1) errors.push(`${part.id}: quantity must be at least 1`);
    if (!part.source) errors.push(`${part.id}: source provenance is required`);
  }

  for (const relation of relations) {
    if (!partIds.has(relation.from)) errors.push(`Unknown relation source: ${relation.from}`);
    if (!partIds.has(relation.to)) errors.push(`Unknown relation target: ${relation.to}`);
    if (relation.from === relation.to) errors.push(`Self relation is not allowed: ${relation.from}`);
  }

  return errors;
}
