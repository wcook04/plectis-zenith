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
    note: 'The graph as it is written in the repository today.',
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
  idea: 'Section 1, A competent investigator', lab: 'Section 2, One measured repair',
  oracle: 'Section 2, Review', trace: 'Section 2, Controlled replay',
  research: 'Section 4, Scope and next evidence', results: 'Section 4, Measured results',
};

export const HERO = {
  lede: 'Can an investigator improve a reusable procedure by testing a diagnosis of its own work?',
  question: 'Zenith runs an adaptive Lab, reviews its recorded evidence, and tests exact procedure changes. The current results separate cheap-model competence from unreliable review and unchanged forecasts. Historical graph views remain available alongside the active method and receipts.',
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
  idea: { kicker: 'The research question', paragraphs: [
    'Lab investigates the evidence available at a cutoff and freezes a decision. Oracle reviews what it actually received and did; Evolve proposes a reusable procedure change when the evidence supports one.',
    'Code reruns the complete investigation under unchanged and candidate procedures and supplies the measured consequence to the next review. Successful execution, changed behaviour, useful decisions and transfer are separate claims.',
    'The next task must support a useful decision with the available information. Ranking, investigation selection and forecast triage are candidates; the historical market case remains a stress test.',
  ] },
  lab: { kicker: 'Investigate before deciding', paragraphs: [
    'The active Lab is one adaptive investigator. It chooses inspect, compare or commit after seeing the previous numerical result. The CLI records the actual actions and exact supplied contexts.',
    'Code owns the target identities, cutoffs, numerical recipes and reference forecasts. A small interpretation calibration checks basic distinctions before a larger learning experiment.',
    'The older multi-stage graph shown in retained viewers is historical evidence. A larger graph must earn its cost against the adaptive controller and strong numerical baselines.',
  ] },
  oracle: { kicker: 'Locate a supported defect', paragraphs: [
    'The reviewer receives the executed graph, reconstructible original contexts, numerical receipts and separately labelled later outcomes. A lossless evidence bank removes repeated copies without truncating the record.',
    'A wrong outcome does not locate a reasoning error. Diagnosis must distinguish missing information, missing inputs, inadequate actions, faulty interpretation and execution failure. No supported defect is a valid result.',
  ] },
  evolve: { kicker: 'Test one exact change', paragraphs: [
    'Diagnosis and proposal share one response. The editable object is a complete reusable investigation procedure. The model cannot silently change the tools, outcome or evaluator.',
    'The candidate and unchanged procedure both rerun from the same snapshot. Measured actions and task outcomes reach the next review. Nothing is adopted automatically; useful learning requires protected cases and controls for ordinary variation.',
  ] },
  results: { kicker: 'What actually ran', paragraphs: [
    'The original episode completed without improving forecasts. Subsequent cheap-model checks passed simple interpretation questions, but long-context reviewers still made unsupported claims.',
    'The linked receipts retain costs, failures and interface versions. Correct semantic answers in the wrong output shape remain a format failure. Calibration does not establish predictive or learning benefit.',
  ] },
  'results:verified_preparation': { kicker: 'Historical fixture preparation', paragraphs: [
    'The retained System A fixture uses invented observations. Its preparation receipt loaded inputs and prepared a request without inference. It is separate from the later adaptive-investigator experiments.',
  ] },
  next: { kicker: 'A decisive next experiment', paragraphs: [
    'Choose a useful task with sufficient available information and a verifiable outcome. Identify why language adds value over code, then compare the smallest plausible architectures under matched observations and budgets.',
    'Freeze a procedure and evaluation before testing a model-authored repair on protected further cases. Keep proposal-search cost, format failures, regressions and no-change outcomes in the record.',
    'Novelty and practical advantage remain open. Cheap inference makes disciplined experiments affordable; it does not establish that a particular graph or learning mechanism works.',
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
