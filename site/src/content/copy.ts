// Teaching copy for each chapter served by /api/v1/site. The wording follows
// paper/zenith.tex; measured numbers are never written here. They are read
// from the public receipts at runtime.

export const EVIDENCE_KIND_LABEL: Record<string, { label: string; note: string }> = {
  proposed_process: {
    label: 'Proposed procedure',
    note: 'A proposed procedure; execution and useful improvement are separate claims.',
  },
  authored_mechanism: {
    label: 'Defined in the code',
    note: 'The procedure implemented in the repository today.',
  },
  measured_experiment: { label: 'Measured experiment', note: 'Saved execution evidence; not necessarily an improvement.' },
  measured_execution: {
    label: 'Measured run',
    note: 'What actually ran, read from saved results.',
  },
  verified_preparation: {
    label: 'Checked preparation',
    note: 'The inputs were loaded and the first request was prepared. No model output exists.',
  },
  research_proposal: {
    label: 'Research question',
    note: 'A question that needs evidence before adoption.',
  },
};

export const SECTION_LABEL: Record<string, string> = {
  idea: 'The research question', lab: 'The native observation task',
  oracle: 'Measured repair', trace: 'Frozen prediction programs',
  research: 'Interpretation and next evidence', results: 'Measured comparisons',
};

export const HERO = {
  lede: 'Can an earlier investigation improve the next one?',
  question: 'A research prototype that writes tests, measures failures and repairs code. The goal is to learn better ways to investigate the next problem.',
};

// Counts come from the graph the backend serves, never from this file.
export type GraphFacts = {
  total: number;
  feeds: number;
  acquired: string[];
  real: string[];
  synthetic: string[];
  reasoning: number;
  miners: number;
};

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];
export const numberWord = (n: number) => WORDS[n] ?? String(n);
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const list = (items: string[]) =>
  items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;

export function labParagraphs(f: GraphFacts | null): string[] {
  if (!f) return CHAPTER_COPY.lab.paragraphs;
  const edition = ' This historical demonstration uses only invented observations of System A; derived summaries are computed from those observations.';
  return [
    `The retained historical graph has ${f.total} nodes: ${numberWord(f.feeds)} data feeds and ${f.reasoning} reasoning steps. ${capital(numberWord(f.acquired.length))} feeds are source observations (${list(f.acquired)}), and a tool computes summaries from measurements, subsystem readings and context.${edition}`,
    `${capital(numberWord(f.miners))} miners, one for each feed, each extract the main signals from their feed. The first synthesis maps where their findings agree and conflict, Orient builds causal hypotheses, and Decide freezes a thesis as checkpoint CP1. A second, directed pass re-reads every feed for that thesis before the Director freezes predictions at CP2. Integrity then audits both passes.`,
    CHAPTER_COPY.lab.paragraphs[0],
  ];
}

export const CHAPTER_COPY: Record<string, { kicker: string; paragraphs: string[] }> = {
  idea: { kicker: 'Knowledge that can do work', paragraphs: [
    'An observed counterexample can require a different computation. Retain useful alternative programs, measured failures and the evidence on which predictions depend.',
    'The current study asks what a native SQLite channel measures. A counter can include rolled-back changes or auxiliary writes even when committed item count stays unchanged.',
  ] },
  lab: { kicker: 'Measure an unfamiliar source', paragraphs: [
    'The model proposes action sequences. The host executes disposable native SQLite experiments and records the channel alongside separately read committed count and value sum.',
    'Every construction policy receives the same observed transcript. Model-written Python predicts new action combinations; a restricted process records its acquired history and execution errors.',
  ] },
  oracle: { kicker: 'Make failure observable', paragraphs: [
    'Measured calibration outputs check each proposed program. Rejected candidates and their execution errors remain available to the next repair request.',
    'Development selection permits valid neutral revisions and reports regressions. Protected compositions are evaluated only after every construction call has finished; source identification remains conditional on the frozen native family.',
  ] },
  evolve: { kicker: 'Freeze before comparison', paragraphs: [
    'Incremental repair sees the latest challenger; archive construction retains earlier attempts; the fresh compiler starts with final evidence. All receive the same proposal allowance and executable interface.',
    'Freeze every checkpoint before protected evaluation. A first-checkpoint control, empty-history replay and unlearned program test what the final computation and supplied observations contribute.',
  ] },
  results: { kicker: 'Replay the evidence', paragraphs: [
    'The table below shows the initial native comparison. Follow-on receipts and the repository explanation compare fresh reconstruction, complementary candidate pools, new observations, archive selection and composition.',
    'Complete receipts compare frozen exact answers, unsupported commitments and execution errors. Configured native sources are conditional replications in one software family, not independent domains.',
  ] },
  'results:verified_preparation': { kicker: 'Historical fixture preparation', paragraphs: [
    'The retained System A fixture uses invented observations. Its preparation receipt loaded inputs and prepared a request without inference.',
  ] },
  next: { kicker: 'Make the knowledge cumulative', paragraphs: [
    'Test transfer to independently implemented sources and misleading near-matches. A bounded native comparison cannot by itself establish broad semantic discovery or lifetime economic value.',
    'Compare complete evidence, execution and inference costs. Preserve unresolved goals and failed attempts when the current computation does not support a new conclusion.',
  ] },
};

export const LOOP_STAGES = [
  {
    id: 'feeds',
    side: 'before',
    title: 'Earlier evidence',
    detail: 'Feeds saved at the cutoff',
    receives: 'The source observations and derived summaries, exactly as saved at time t.',
    produces: 'A fixed input universe. Anything absent here was unavailable to the run.',
  },
  {
    id: 'lab',
    side: 'before',
    title: 'Lab',
    detail: 'Inspect, compare, commit',
    receives: 'Only the saved feeds and its own earlier outputs.',
    produces: 'An action trace, numerical receipts and a frozen complete decision.',
  },
  {
    id: 'frozen',
    side: 'boundary',
    title: 'Frozen prediction',
    detail: 'Sealed before outcome',
    receives: 'The completed Lab commitment.',
    produces: 'A record nobody may edit after later evidence is revealed.',
  },
  {
    id: 'later',
    side: 'after',
    title: 'Later evidence',
    detail: 'Same sources after the horizon',
    receives: 'The same sources, captured after the horizon.',
    produces: 'What actually happened, for comparison only.',
  },
  {
    id: 'oracle',
    side: 'after',
    title: 'Oracle',
    detail: 'Compare and diagnose',
    receives: 'The frozen record, the feeds the Lab saw, and the later feeds.',
    produces: 'A supported diagnosis or no change, with evidence and an alternative explanation.',
  },
  {
    id: 'evolve',
    side: 'after',
    title: 'Evolve',
    detail: 'Propose one change',
    receives: 'Oracle’s report.',
    produces: 'One exact reusable procedure replacement, recorded as a candidate version.',
  },
  {
    id: 'compare',
    side: 'test',
    title: 'Compare on another window',
    detail: 'Original and revision, same later inputs',
    receives: 'Both versions and later cases nobody used to choose the revision.',
    produces: 'Gains and regressions under a score fixed in advance. Protected-case improvement remains unproved.',
  },
] as const;

export const DIAGNOSIS_ROWS = [
  ['Evidence unavailable', 'Was the relevant information absent from the saved input universe?'],
  ['Evidence not supplied', 'Was it in that universe but missing from the node’s actual input?'],
  ['Reasoning error', 'Did the node receive the evidence but draw an unsupported conclusion?'],
  ['Execution failure', 'Did truncation, parsing or another runtime error prevent a usable output?'],
] as const;
