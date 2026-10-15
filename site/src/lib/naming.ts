// Display names for native node ids. Ids stay unchanged everywhere they are
// data; these names are presentation only and follow the paper's vocabulary
// ("Synthesis" is the paper's word for the Cross-correlation nodes).
import { laneLabel, laneName } from './lanes';

const LANE_TOKEN: Record<string, string> = {
  measurements: 'MEASUREMENTS',
  subsystems: 'SUBSYSTEMS',
  environment: 'ENVIRONMENT',
  events: 'EVENTS',
  interventions: 'INTERVENTIONS',
  derived: 'DERIVED',
};

const FIXED: Record<string, string> = {
  global_derived_feed: 'Derived summaries',
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
  oracle_truth_diff_observations: 'Observation differences',
  oracle_truth_diff_environment: 'Environment differences',
  oracle_truth_map: 'Evidence summary',
  oracle_attribution_map: 'Failure hypothesis',
  oracle_explain: 'Later context',
  oracle_cp2_emitter: 'Oracle report',
  delta_analyzer: 'Delta analyser',
  dossier_updater: 'Instruction updater',
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
    family: { key: 'feeds', label: 'Saved feeds', summary: 'Source observations and computed summaries' },
  },
  {
    test: /^lab_miner_v2_/,
    family: { key: 'miners_v2', label: 'Directed miners', summary: 'Re-read each data source for the saved explanation' },
  },
  {
    test: /^lab_miner_/,
    family: { key: 'miners', label: 'First-pass miners', summary: 'One reader for each data feed' },
  },
  {
    test: /^oracle_subject_\w+_feed$/,
    family: { key: 'subject_feeds', label: 'Earlier feeds', summary: 'The feeds the Lab saw at its cutoff' },
  },
  {
    test: /^oracle_subject_(index|lab_)/,
    family: { key: 'subject_lab', label: 'Saved Lab record', summary: 'The saved predictions Oracle compares with later observations' },
  },
  {
    test: /^oracle_truth_diff_/,
    family: { key: 'diffs', label: 'Numeric differences', summary: 'Before and after, computed without a model' },
  },
  {
    test: /^oracle_truth_(measurements|subsystems|environment|events|interventions|derived)$/,
    family: { key: 'lane_reviews', label: 'Source reviews', summary: 'What each data source shows after the cutoff' },
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
  global_derived_feed: 'Summaries computed from the earlier observations',
  lab_seed_state: 'Maps what data exists and what is missing',
  lab_cross_corr_v1: 'Combines agreements and conflicts between data sources',
  lab_cross_corr_v2: 'Combines evidence about the selected measurements',
  lab_orient: 'Ranks possible explanations for the observations',
  lab_decide: 'Saves one explanation before seeing later observations',
  lab_director: 'Saves predictions of which measurements will rise or fall',
  lab_integrity: 'Looks for contradictions and unsupported claims',
  oracle_subject_index: 'Identifies the earlier Lab execution being reviewed',
  oracle_subject_lab_cross_corr_v2: 'The Lab’s second synthesis',
  oracle_subject_lab_decide: 'The Lab’s saved explanation',
  oracle_subject_lab_director: 'The Lab’s saved predictions',
  oracle_truth_diff_observations: 'Target values before and after',
  oracle_truth_diff_environment: 'Environment before and after',
  oracle_truth_map: 'Combines the source reviews',
  oracle_attribution_map: 'Suggests why earlier predictions were wrong',
  oracle_explain: 'Additional observations that may explain prediction errors',
  oracle_cp2_emitter: 'Saves the comparison of predictions and later observations',
  delta_analyzer: 'Which parts of an instruction to change',
  dossier_updater: 'Writes the exact patch',
  version_committer: 'Applies it as a new version',
};

export function nodeRole(id: string, mission = 'lab'): string {
  if (ROLE[id]) return ROLE[id];
  let m = /^global_(\w+?)_feed$/.exec(id);
  if (m) return mission === 'oracle' ? 'Captured after the cutoff' : 'Saved at the cutoff';
  m = /^lab_miner_v2_(\w+)$/.exec(id);
  if (m) return `Re-reads ${laneName(LANE_TOKEN[m[1]] ?? m[1])} for the saved explanation`;
  m = /^lab_miner_(\w+)$/.exec(id);
  if (m) return `Reads observations from ${laneName(LANE_TOKEN[m[1]] ?? m[1])}`;
  m = /^oracle_subject_(\w+?)_feed$/.exec(id);
  if (m) return 'As the Lab saw it';
  m = /^oracle_truth_(\w+)$/.exec(id);
  if (m) return 'What this source shows later';
  return '';
}

export const CHECKPOINTS = new Set(['lab_decide', 'lab_director', 'oracle_cp2_emitter']);
