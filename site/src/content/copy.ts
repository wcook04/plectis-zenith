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
  idea: 'Section 1, Knowledge that can do work', lab: 'Section 1, The operational task',
  oracle: 'Section 2, Repair and reuse', trace: 'Section 2, Frozen procedures',
  research: 'Section 4, Interpretation and next evidence', results: 'Section 4, Measured evidence',
};

export const HERO = {
  lede: 'Can a measured failure become a computation that keeps working?',
  question: 'Zenith turns operational investigations into reusable programs. Lab executes, Oracle measures the errors, and Evolve proposes a repair. New cases test whether that computation survives beyond the examples used to develop it.',
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
    'Retain an executable investigation, its scope and the counterexamples used to repair it. The next case can use that computation without buying the same reasoning again.',
    'An answer can contain supported findings and unresolved checks together. Duplicated telemetry does not rule out a real regression; missing requests can prevent a numerical conclusion while other findings remain valid.',
  ] },
  lab: { kicker: 'Compute the requested quantity', paragraphs: [
    'Acquire operation intervals and request populations. Read the quantity contract: active time, elapsed time and billed work treat overlap and idle gaps differently.',
    'The model authors Python; a restricted process executes it and records acquired tables. Source contracts, units, repeated records and workload proportions must survive the calculation.',
  ] },
  oracle: { kicker: 'Make failure observable', paragraphs: [
    'An independent evaluator compares the actual findings, unresolved conditions and numerical ratio with the expected answer. The next request receives measured witnesses, including rejected programs and their execution errors.',
    'The full development suite determines whether a proposal improves the incumbent without breaking previously correct cases. A plausible explanation alone cannot pass that test.',
  ] },
  evolve: { kicker: 'Keep a tested computation', paragraphs: [
    'Freeze the accepted program before evaluating further cases. A renamed-schema test may change field bindings, but it cannot rewrite the numerical solver.',
    'The first model proposal, unchanged incumbent, direct answers and prose-memory answers remain comparison controls. Compilation, improvement during development and real-world transfer are separate claims.',
  ] },
  results: { kicker: 'Replay the evidence', paragraphs: [
    'The table below reads versioned campaign receipts. Each complete campaign reports every learner, including failures; the first learner is the declared primary comparison.',
    'Published programs, input tables, evaluator and execution harness replay offline. These are synthetic combinations of known factors, not independent real-world problems.',
  ] },
  'results:verified_preparation': { kicker: 'Historical fixture preparation', paragraphs: [
    'The retained System A fixture uses invented observations. Its preparation receipt loaded inputs and prepared a request without inference.',
  ] },
  next: { kicker: 'Make the knowledge cumulative', paragraphs: [
    'Compare equal-tool, equal-budget learners on new semantic contracts and real operational data with obtainable answers. Test whether retained procedures reduce discovery cost without hiding changed applicability.',
    'Extend the library when one program is demonstrably insufficient. Preserve scope counterexamples and revoke dependent conclusions when their evidence stops supporting them.',
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
