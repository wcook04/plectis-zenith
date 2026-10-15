// Each lane is one perspective on the same observed system.
export const LANE_ORDER = ['MEASUREMENTS', 'SUBSYSTEMS', 'ENVIRONMENT', 'SPINE', 'EVENTS', 'INTERVENTIONS', 'DERIVED'] as const;
export const LANE_LABEL: Record<string, string> = {
  MEASUREMENTS: 'Measurements', SUBSYSTEMS: 'Subsystems', ENVIRONMENT: 'Context',
  SPINE: 'Main path', EVENTS: 'Events', INTERVENTIONS: 'Interventions', DERIVED: 'Derived summaries',
};
export function laneIndex(lane: string): number {
  const index = (LANE_ORDER as readonly string[]).indexOf(lane);
  return index === -1 ? LANE_ORDER.indexOf('SPINE') : index;
}
export function laneColor(lane: string): string {
  return lane === 'SPINE' || !LANE_LABEL[lane] ? 'var(--ink)' : `var(--lane-${lane.toLowerCase()})`;
}
export function laneLabel(lane: string): string { return LANE_LABEL[lane] ?? lane; }
export function laneName(lane: string): string { return laneLabel(lane).toLowerCase(); }
