// Lane vocabulary and row order, adapted from the original Zenith GraphViewer
// (ai_workflow system/server/ui/src/components/GraphViewer.tsx, LANE_ORDER).
// Colours are CSS custom properties defined per theme in styles/tokens.css and
// validated as a categorical palette in both themes. Every lane also prints
// its name, so colour never carries identity alone.

export const LANE_ORDER = [
  'STOCK',
  'ETF',
  'STOCKGRID',
  'MACRO',
  'SPINE',
  'NEWS',
  'POLYMARKET',
  'CALCULATOR',
] as const;

export const LANE_LABEL: Record<string, string> = {
  STOCK: 'Stocks',
  ETF: 'ETFs',
  STOCKGRID: 'Flows',
  MACRO: 'Macro',
  SPINE: 'Main path',
  NEWS: 'News',
  POLYMARKET: 'Prediction markets',
  CALCULATOR: 'Calculator',
};

export function laneIndex(lane: string): number {
  const index = (LANE_ORDER as readonly string[]).indexOf(lane);
  return index === -1 ? LANE_ORDER.indexOf('SPINE') : index;
}

export function laneColor(lane: string): string {
  return lane === 'SPINE' || !LANE_LABEL[lane] ? 'var(--ink)' : `var(--lane-${lane.toLowerCase()})`;
}

export function laneLabel(lane: string): string {
  return LANE_LABEL[lane] ?? lane;
}

// The lane's name inside a sentence: lower case except for acronyms.
export function laneName(lane: string): string {
  const label = laneLabel(lane);
  return label === 'ETFs' ? label : label.toLowerCase();
}
