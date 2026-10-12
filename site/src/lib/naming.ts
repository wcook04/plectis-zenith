// Display names for native node ids. Ids stay unchanged everywhere they are
// data; these names are presentation only and follow the paper's vocabulary
// ("Synthesis" is the paper's word for the Cross-correlation nodes).
import { laneLabel, laneName } from './lanes';

const LANE_TOKEN: Record<string, string> = {
  stock: 'STOCK',
  etf: 'ETF',
  macro: 'MACRO',
  news: 'NEWS',
  poly: 'POLYMARKET',
  polymarket: 'POLYMARKET',
  calc: 'CALCULATOR',
  calculator: 'CALCULATOR',
  stockgrid: 'STOCKGRID',
};

const FIXED: Record<string, string> = {
  global_calculator_feed: 'Calculator',
  lab_seed_state: 'Seed state',
  lab_cross_corr_v1: 'Synthesis 1',
  lab_cross_corr_v2: 'Synthesis 2',
  lab_orient: 'Orient',
  lab_decide: 'Decide (CP1)',
  lab_director: 'Director (CP2)',
  lab_integrity: 'Integrity',
  oracle_subject_index: 'Saved run index',
  oracle_subject_lab_cross_corr_v2: 'Saved Synthesis 2',
  oracle_subject_lab_decide: 'Saved CP1',
  oracle_subject_lab_director: 'Saved CP2',
  oracle_truth_diff_equity: 'Equity differences',
  oracle_truth_diff_macro: 'Macro differences',
  oracle_truth_map: 'Evidence summary',
  oracle_attribution_map: 'Failure hypothesis',
  oracle_explain: 'Later context',
  oracle_cp2_emitter: 'Oracle report',
  delta_analyzer: 'Delta analyser',
  dossier_updater: 'Dossier updater',
  version_committer: 'Version committer',
};

function lane(token: string): string {
  return laneLabel(LANE_TOKEN[token] ?? token.toUpperCase());
}

export function nodeName(id: string): string {
  if (FIXED[id]) return FIXED[id];
  let m = /^global_(\w+?)_feed$/.exec(id);
  if (m) return `${lane(m[1])} feed`;
  m = /^lab_miner_v2_(\w+)$/.exec(id);
  if (m) return `${lane(m[1])} directed miner`;
  m = /^lab_miner_(\w+)$/.exec(id);
  if (m) return `${lane(m[1])} miner`;
  m = /^oracle_subject_(\w+?)_feed$/.exec(id);
  if (m) return `Saved ${lane(m[1]).toLowerCase()} feed`;
  m = /^oracle_truth_(\w+)$/.exec(id);
  if (m) return `${lane(m[1])} review`;
  return id.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

// Families group the lane-parallel siblings the reader can expand or collapse.
export type Family = { key: string; label: string; summary: string };

const FAMILIES: Array<{ test: RegExp; family: Family }> = [
  {
    test: /^global_\w+_feed$/,
    family: { key: 'feeds', label: 'Saved feeds', summary: 'Acquired feeds and the derived calculator' },
  },
  {
    test: /^lab_miner_v2_/,
    family: { key: 'miners_v2', label: 'Directed miners', summary: 'Re-read each feed for the frozen thesis' },
  },
  {
    test: /^lab_miner_/,
    family: { key: 'miners', label: 'First-pass miners', summary: 'One feed-specific reader per lane' },
  },
  {
    test: /^oracle_subject_\w+_feed$/,
    family: { key: 'subject_feeds', label: 'Earlier feeds', summary: 'The feeds the Lab saw at its cutoff' },
  },
  {
    test: /^oracle_subject_(index|lab_)/,
    family: { key: 'subject_lab', label: 'Saved Lab record', summary: 'The frozen run Oracle reviews' },
  },
  {
    test: /^oracle_truth_diff_/,
    family: { key: 'diffs', label: 'Numeric differences', summary: 'Before and after, computed without a model' },
  },
  {
    test: /^oracle_truth_(stock|etf|macro|news|poly|calc|stockgrid)$/,
    family: { key: 'lane_reviews', label: 'Lane reviews', summary: 'What each lane shows after the cutoff' },
  },
];

export function nodeFamily(id: string, mission = 'lab'): Family | null {
  if (mission === 'oracle' && /^global_\w+_feed$/.test(id)) {
    return { key: 'feeds', label: 'Later feeds', summary: 'The same sources, after the cutoff' };
  }
  for (const { test, family } of FAMILIES) if (test.test(id)) return family;
  return null;
}

// One plain line under each card, paraphrasing the node's authored purpose.
const ROLE: Record<string, string> = {
  global_calculator_feed: 'Regime metrics from stocks, ETFs, macro',
  lab_seed_state: 'Maps what data exists and what is missing',
  lab_cross_corr_v1: 'Where the miners agree and conflict',
  lab_cross_corr_v2: 'Where evidence converges on targets',
  lab_orient: 'Builds and ranks causal hypotheses',
  lab_decide: 'Freezes one dominant thesis',
  lab_director: 'Freezes directional predictions',
  lab_integrity: 'Audits the reasoning of both passes',
  oracle_subject_index: 'Grounding context from the paired Lab run',
  oracle_subject_lab_cross_corr_v2: 'The Lab’s second synthesis',
  oracle_subject_lab_decide: 'The Lab’s frozen thesis',
  oracle_subject_lab_director: 'The Lab’s frozen predictions',
  oracle_truth_diff_equity: 'Stock and ETF before and after',
  oracle_truth_diff_macro: 'Macro before and after',
  oracle_truth_map: 'Combines the lane reviews',
  oracle_attribution_map: 'Maps what happened onto the Lab’s evidence',
  oracle_explain: 'Optional later context for misses',
  oracle_cp2_emitter: 'Records the reconstruction for review',
  delta_analyzer: 'Which dossier sections to change',
  dossier_updater: 'Writes the exact patch',
  version_committer: 'Applies it as a new version',
};

export function nodeRole(id: string, mission = 'lab'): string {
  if (ROLE[id]) return ROLE[id];
  let m = /^global_(\w+?)_feed$/.exec(id);
  if (m) return mission === 'oracle' ? 'Captured after the cutoff' : 'Saved at the cutoff';
  m = /^lab_miner_v2_(\w+)$/.exec(id);
  if (m) return `Re-reads ${laneName(LANE_TOKEN[m[1]] ?? m[1])} for the thesis`;
  m = /^lab_miner_(\w+)$/.exec(id);
  if (m) return `Extracts signals from ${laneName(LANE_TOKEN[m[1]] ?? m[1])}`;
  m = /^oracle_subject_(\w+?)_feed$/.exec(id);
  if (m) return 'As the Lab saw it';
  m = /^oracle_truth_(\w+)$/.exec(id);
  if (m) return 'What this lane shows later';
  return '';
}

export const CHECKPOINTS = new Set(['lab_decide', 'lab_director', 'oracle_cp2_emitter']);
