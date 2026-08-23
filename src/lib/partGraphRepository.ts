import {
  getRepairBlock,
  getRepairGraph,
  publishedRepairGraphs,
  repairBlocks,
  type RepairBlockDefinition,
  type RepairBlockId,
  type RepairGraphDefinition,
} from '../data/partGraphSystems';
import type {PartNode, PartRelation} from '../data/partGraphDemo';

export const PARTGRAPH_DB_VERSION = '2026.08.23.1';

export interface HardwareAttachment {
  part: PartNode;
  relation: PartRelation;
  relationLabel: string;
}

const relationLabels: Record<PartRelation['type'], string> = {
  mounted_by: 'mounts this part',
  fastened_by: 'fastens this part',
  seated_on: 'seals / seats this part',
  fluid_connected_to: 'seals / connects this circuit',
  attached_to: 'attaches to this part',
  adjacent_to: 'sits beside this part',
  serviced_with: 'used while servicing',
  inspect_when_servicing: 'inspect while servicing',
};

export function listRepairBlocks(): RepairBlockDefinition[] {
  return repairBlocks;
}

export function listSubBlocks(blockId: RepairBlockId): RepairGraphDefinition[] {
  return getRepairBlock(blockId).graphs;
}

export function readRepairGraph(graphId: string): RepairGraphDefinition {
  return getRepairGraph(graphId);
}

export function listTargetParts(graph: RepairGraphDefinition): PartNode[] {
  return graph.parts.filter((part) => part.category !== 'fastener');
}

export function isIntegratedHardware(part: PartNode): boolean {
  return part.category === 'fastener';
}

export function hardwareForPart(graph: RepairGraphDefinition, parentPartId: string): HardwareAttachment[] {
  const byId = new Map(graph.parts.map((part) => [part.id, part]));
  const hardware: HardwareAttachment[] = [];

  for (const relation of graph.relations) {
    let candidateId: string | null = null;
    if (relation.from === parentPartId) candidateId = relation.to;
    if (relation.to === parentPartId) candidateId = relation.from;
    if (!candidateId) continue;

    const candidate = byId.get(candidateId);
    if (!candidate || !isIntegratedHardware(candidate)) continue;

    hardware.push({
      part: candidate,
      relation,
      relationLabel: relationLabels[relation.type],
    });
  }

  return hardware.sort((a, b) => a.part.name.localeCompare(b.part.name));
}

export function visibleAssemblyParts(graph: RepairGraphDefinition): PartNode[] {
  return graph.parts.filter((part) => !isIntegratedHardware(part));
}

export function orphanHardware(graph: RepairGraphDefinition): PartNode[] {
  const parented = new Set<string>();
  for (const part of visibleAssemblyParts(graph)) {
    for (const attachment of hardwareForPart(graph, part.id)) parented.add(attachment.part.id);
  }
  return graph.parts.filter((part) => isIntegratedHardware(part) && !parented.has(part.id));
}

export function validateRepository(): string[] {
  const errors: string[] = [];
  const graphIds = new Set<string>();

  for (const graph of publishedRepairGraphs) {
    if (graphIds.has(graph.id)) errors.push(`Duplicate graph id: ${graph.id}`);
    graphIds.add(graph.id);
    if (!graph.parts.some((part) => part.id === graph.defaultTargetPartId)) {
      errors.push(`${graph.id}: default target part does not exist`);
    }
  }

  return errors;
}
