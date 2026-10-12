// Deterministic wave-by-lane layout for native mission graphs.
//
// Adapted from the original Zenith GraphViewer (ai_workflow
// system/server/ui/src/components/GraphViewer.tsx): execution waves become
// columns, lanes become rows around the main path, and lane-parallel siblings
// collapse into one container until the reader expands them. Differences from
// the original: collapsed containers sit on the main path so the overview
// reads as one line; expanded siblings stay contiguous inside their column so
// a group frame never encloses an unrelated node; empty columns are removed.
import type { Graph, GraphNode } from '../../api';
import { laneIndex, LANE_ORDER } from '../../lib/lanes';
import { nodeFamily, type Family } from '../../lib/naming';

export const NODE_W = 200;
export const NODE_H = 94;
export const GROUP_H = 100;
export const COL_W = 264;
const ROW_H = NODE_H + 18;
const MAX_BAND_COLUMNS = 7;
const BAND_LABEL_H = 44;
const BAND_GAP = 36;
const CHANNEL_PAD = 10;
const CHANNEL_STEP = 7;
const MAX_SLOTS = 14;
const MEMBER_GAP = 10;
const BLOCK_GAP = 28;
const SPINE_ROW = LANE_ORDER.indexOf('SPINE');

export type NodeItem = {
  kind: 'node';
  id: string;
  node: GraphNode;
  column: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type GroupItem = {
  kind: 'group';
  id: string;
  family: Family;
  members: GraphNode[];
  lanes: string[];
  column: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type FrameItem = {
  kind: 'frame';
  id: string;
  family: Family;
  members: string[];
  x: number;
  y: number;
  w: number;
  h: number;
};

export type LayoutEdge = {
  id: string;
  source: string;
  target: string;
  lane: string;
  skip: boolean;
  // Routed edges skip a step or cross into the next band. They leave through
  // the gap right of their source column, run in the channel above the
  // target's band, and enter through the gap left of their target column.
  routed: boolean;
  // A skip edge whose dependency is already implied by another path. Hidden
  // in the overview unless the reader asks for every dependency, as in the
  // original GraphViewer's showAllDependencies switch.
  redundant: boolean;
  channelY: number;
  // Edges into the same target share one trunk: one exit lane per target in
  // the source column's gap and one channel row per target, so a bundle reads
  // as a bus with branches instead of parallel near-duplicate lines.
  slot: number;
  outLane: number;
  rawIds: string[];
};

export type BandLabel = { id: string; title: string; detail: string; y: number };

export type GraphLayout = {
  items: Array<NodeItem | GroupItem>;
  frames: FrameItem[];
  edges: LayoutEdge[];
  bands: BandLabel[];
  renderIdOf: Map<string, string>;
  columnCount: number;
  families: Map<string, { family: Family; members: string[] }>;
};

type Unit = {
  id: string;
  wave: number;
  targetCenter: number;
  h: number;
  blockKey: string;
  sortRow: number;
  build: (column: number, x: number, y: number) => NodeItem | GroupItem;
};

export function familiesOf(graph: Graph): Map<string, { family: Family; members: string[] }> {
  const families = new Map<string, { family: Family; members: string[] }>();
  graph.nodes.forEach((node) => {
    const family = nodeFamily(node.id, graph.mission);
    if (!family) return;
    if (!families.has(family.key)) families.set(family.key, { family, members: [] });
    families.get(family.key)!.members.push(node.id);
  });
  // A family of one is just a node.
  families.forEach((entry, key) => {
    if (entry.members.length < 2) families.delete(key);
  });
  return families;
}

export function layoutGraph(graph: Graph, expanded: ReadonlySet<string>): GraphLayout {
  const waveOf = new Map<string, number>();
  graph.waves.forEach((wave, index) => wave.forEach((id) => waveOf.set(id, index)));
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const families = familiesOf(graph);
  const familyKeyOf = new Map<string, string>();
  families.forEach((entry, key) => entry.members.forEach((id) => familyKeyOf.set(id, key)));

  const units: Unit[] = [];
  const renderIdOf = new Map<string, string>();
  const spineCenter = SPINE_ROW * ROW_H + NODE_H / 2;

  families.forEach((entry, key) => {
    if (expanded.has(key)) return;
    const members = entry.members.map((id) => byId.get(id)!).sort(byLaneThenId);
    const id = `group:${key}`;
    members.forEach((member) => renderIdOf.set(member.id, id));
    units.push({
      id,
      wave: Math.min(...members.map((m) => waveOf.get(m.id) ?? 0)),
      targetCenter: spineCenter,
      h: GROUP_H,
      blockKey: id,
      sortRow: SPINE_ROW,
      build: (column, x, y) => ({
        kind: 'group',
        id,
        family: entry.family,
        members,
        lanes: Array.from(new Set(members.map((m) => m.lane))),
        column,
        x,
        y,
        w: NODE_W,
        h: GROUP_H,
      }),
    });
  });

  graph.nodes.forEach((node) => {
    if (renderIdOf.has(node.id)) return;
    renderIdOf.set(node.id, node.id);
    const familyKey = familyKeyOf.get(node.id);
    const row = laneIndex(node.lane);
    units.push({
      id: node.id,
      wave: waveOf.get(node.id) ?? 0,
      targetCenter: row * ROW_H + NODE_H / 2,
      h: NODE_H,
      blockKey: familyKey ? `family:${familyKey}` : node.id,
      sortRow: row,
      build: (column, x, y) => ({ kind: 'node', id: node.id, node, column, x, y, w: NODE_W, h: NODE_H }),
    });
  });

  // An expanded family keeps its members in one column block: place it at the
  // first wave any member occupies.
  const blockWave = new Map<string, number>();
  units.forEach((unit) => {
    const current = blockWave.get(unit.blockKey);
    blockWave.set(unit.blockKey, current === undefined ? unit.wave : Math.min(current, unit.wave));
  });
  units.forEach((unit) => {
    unit.wave = blockWave.get(unit.blockKey) ?? unit.wave;
  });

  const waves = Array.from(new Set(units.map((u) => u.wave))).sort((a, b) => a - b);
  const columnOfWave = new Map(waves.map((wave, index) => [wave, index]));

  // Long graphs wrap into bands so the overview stays readable. The Lab
  // breaks where the paper's Figure 2 does: before the directed second pass.
  const columnCount = waves.length;
  let breakAt = -1;
  const secondPass = units.find((u) => u.id === 'group:miners_v2' || u.blockKey === 'family:miners_v2');
  if (secondPass && columnCount > MAX_BAND_COLUMNS) breakAt = columnOfWave.get(secondPass.wave) ?? -1;
  else if (columnCount > MAX_BAND_COLUMNS) breakAt = Math.ceil(columnCount / 2);
  const bandOf = (column: number) => (breakAt > 0 && column >= breakAt ? 1 : 0);
  const xOf = (column: number) => (bandOf(column) === 1 ? column - breakAt : column) * COL_W;

  const items: Array<NodeItem | GroupItem> = [];
  const frames: FrameItem[] = [];
  const bandOfItem = new Map<string, number>();

  waves.forEach((wave) => {
    const column = columnOfWave.get(wave)!;
    const x = xOf(column);
    const blocks = new Map<string, Unit[]>();
    units
      .filter((u) => u.wave === wave)
      .forEach((u) => {
        if (!blocks.has(u.blockKey)) blocks.set(u.blockKey, []);
        blocks.get(u.blockKey)!.push(u);
      });
    const ordered = Array.from(blocks.values())
      .map((members) => {
        members.sort((a, b) => a.sortRow - b.sortRow || a.id.localeCompare(b.id));
        const height = members.reduce((sum, m) => sum + m.h, 0) + MEMBER_GAP * (members.length - 1);
        const target = members.reduce((sum, m) => sum + m.targetCenter, 0) / members.length;
        return { members, height, target };
      })
      .sort((a, b) => a.target - b.target);

    // Stack blocks without overlap, then shift the column so its blocks sit
    // on their targets on average (keeps the main path one straight line).
    let cursor = -Infinity;
    const placed = ordered.map((block) => {
      const top = Math.max(block.target - block.height / 2, cursor === -Infinity ? -Infinity : cursor + BLOCK_GAP);
      cursor = top + block.height;
      return { ...block, top };
    });
    const drift = placed.reduce((sum, b) => sum + (b.top + b.height / 2 - b.target), 0) / placed.length;
    placed.forEach((block) => {
      let y = block.top - drift;
      const blockItems: Array<NodeItem | GroupItem> = [];
      block.members.forEach((member) => {
        const item = member.build(column, x, y);
        blockItems.push(item);
        bandOfItem.set(item.id, bandOf(column));
        y += member.h + MEMBER_GAP;
      });
      items.push(...blockItems);
      const key = block.members[0].blockKey;
      if (key.startsWith('family:') && blockItems.length > 1) {
        const familyKey = key.slice('family:'.length);
        const entry = families.get(familyKey)!;
        const top = Math.min(...blockItems.map((i) => i.y));
        const bottom = Math.max(...blockItems.map((i) => i.y + i.h));
        const id = `frame:${familyKey}`;
        bandOfItem.set(id, bandOf(column));
        frames.push({
          kind: 'frame',
          id,
          family: entry.family,
          members: entry.members,
          x: x - 10,
          y: top - 32,
          w: NODE_W + 20,
          h: bottom - top + 42,
        });
      }
    });
  });

  const columnOf = new Map(items.map((item) => [item.id, item.column]));
  const edgeMap = new Map<string, LayoutEdge>();
  graph.edges.forEach((edge) => {
    const source = renderIdOf.get(edge.source);
    const target = renderIdOf.get(edge.target);
    if (!source || !target || source === target) return;
    const key = `${source}->${target}`;
    const existing = edgeMap.get(key);
    if (existing) {
      existing.rawIds.push(edge.id);
      return;
    }
    const sourceNode = byId.get(edge.source);
    const crossBand = (bandOfItem.get(source) ?? 0) !== (bandOfItem.get(target) ?? 0);
    edgeMap.set(key, {
      id: key,
      source,
      target,
      lane: source.startsWith('group:') ? 'SPINE' : (sourceNode?.lane ?? 'SPINE'),
      skip: (columnOf.get(target) ?? 0) - (columnOf.get(source) ?? 0) > 1,
      routed: crossBand || (columnOf.get(target) ?? 0) - (columnOf.get(source) ?? 0) > 1,
      redundant: false,
      channelY: 0,
      slot: 0,
      outLane: 0,
      rawIds: [edge.id],
    });
  });
  const edges = Array.from(edgeMap.values());

  // Transitive reduction of skip edges (hasAlternatePath in the original).
  const outgoing = new Map<string, LayoutEdge[]>();
  edges.forEach((edge) => {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source)!.push(edge);
  });
  edges.forEach((candidate) => {
    if (!candidate.skip) return;
    const seen = new Set([candidate.source]);
    const queue = [candidate.source];
    while (queue.length && !candidate.redundant) {
      const current = queue.shift()!;
      for (const next of outgoing.get(current) ?? []) {
        if (next === candidate) continue;
        if (next.target === candidate.target) {
          candidate.redundant = true;
          break;
        }
        if (!seen.has(next.target)) {
          seen.add(next.target);
          queue.push(next.target);
        }
      }
    }
  });

  // Each band has a channel above it; routed edges run there, one slot each.
  const bandCount = breakAt > 0 ? 2 : 1;
  const slotsInBand = Array.from({ length: bandCount }, () => 0);
  const slotOfTarget = new Map<string, number>();
  const lanesInColumn = new Map<number, Map<string, number>>();
  edges
    .filter((e) => e.routed)
    .sort((a, b) => (columnOf.get(a.target) ?? 0) - (columnOf.get(b.target) ?? 0) || a.target.localeCompare(b.target))
    .forEach((edge) => {
      const band = bandOfItem.get(edge.target) ?? 0;
      if (!slotOfTarget.has(edge.target)) slotOfTarget.set(edge.target, slotsInBand[band]++);
      edge.slot = slotOfTarget.get(edge.target)!;
      const column = columnOf.get(edge.source) ?? 0;
      if (!lanesInColumn.has(column)) lanesInColumn.set(column, new Map());
      const lanes = lanesInColumn.get(column)!;
      if (!lanes.has(edge.target)) lanes.set(edge.target, lanes.size);
      edge.outLane = lanes.get(edge.target)!;
    });
  const channelHeight = slotsInBand.map((n) => (n === 0 ? 0 : CHANNEL_PAD * 2 + CHANNEL_STEP * Math.min(n, MAX_SLOTS)));

  // Normalise each band to start at zero, then stack bands with their channels.
  const bandTop: number[] = [];
  let offset = 0;
  for (let band = 0; band < bandCount; band++) {
    const inBand = [...items, ...frames].filter((i) => (bandOfItem.get(i.id) ?? 0) === band);
    const minY = Math.min(...inBand.map((i) => i.y));
    const maxY = Math.max(...inBand.map((i) => i.y + i.h));
    offset += (bandCount > 1 ? BAND_LABEL_H : 0) + channelHeight[band];
    bandTop.push(offset);
    inBand.forEach((i) => (i.y += offset - minY));
    offset += maxY - minY + BAND_GAP;
  }
  edges.forEach((edge) => {
    if (!edge.routed) return;
    const band = bandOfItem.get(edge.target) ?? 0;
    edge.channelY = bandTop[band] - CHANNEL_PAD - CHANNEL_STEP * (edge.slot % MAX_SLOTS) - CHANNEL_STEP / 2;
  });

  const bands: BandLabel[] =
    bandCount > 1 && secondPass
      ? [
          { id: 'band:0', title: 'First pass', detail: 'Read every feed, synthesise, freeze a thesis at CP1', y: 0 },
          {
            id: 'band:1',
            title: 'Second pass',
            detail: 'Re-read the feeds for that thesis, freeze predictions at CP2, audit both passes',
            y: bandTop[1] - channelHeight[1] - BAND_LABEL_H,
          },
        ]
      : bandCount > 1
        ? [
            { id: 'band:0', title: 'Steps 1 to ' + breakAt, detail: '', y: 0 },
            { id: 'band:1', title: 'Continued', detail: '', y: bandTop[1] - channelHeight[1] - BAND_LABEL_H },
          ]
        : [];

  // Reading order for keyboard focus: column, then top to bottom.
  items.sort((a, b) => a.column - b.column || a.y - b.y);

  return {
    items,
    frames,
    edges,
    bands,
    renderIdOf,
    columnCount,
    families,
  };
}

function byLaneThenId(a: GraphNode, b: GraphNode): number {
  return laneIndex(a.lane) - laneIndex(b.lane) || a.id.localeCompare(b.id);
}

// Direct and transitive neighbourhoods, computed from the authored edges.
export function neighbourhood(graph: Graph, id: string) {
  const parents = new Map<string, string[]>();
  const children = new Map<string, string[]>();
  graph.edges.forEach((edge) => {
    if (!parents.has(edge.target)) parents.set(edge.target, []);
    parents.get(edge.target)!.push(edge.source);
    if (!children.has(edge.source)) children.set(edge.source, []);
    children.get(edge.source)!.push(edge.target);
  });
  const walk = (start: string, next: Map<string, string[]>) => {
    const seen = new Set<string>();
    const queue = [...(next.get(start) ?? [])];
    while (queue.length) {
      const current = queue.shift()!;
      if (seen.has(current)) continue;
      seen.add(current);
      queue.push(...(next.get(current) ?? []));
    }
    return seen;
  };
  return {
    inputs: new Set(parents.get(id) ?? []),
    consumers: new Set(children.get(id) ?? []),
    ancestors: walk(id, parents),
    descendants: walk(id, children),
  };
}
