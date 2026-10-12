// Teaching copy for each chapter served by /api/v1/site. The wording follows
// paper/zenith.tex; measured numbers are never written here. They are read
// from the public receipts at runtime.

export const EVIDENCE_KIND_LABEL: Record<string, { label: string; note: string }> = {
  proposed_process: {
    label: 'Proposed procedure',
    note: 'How the loop is meant to work. The full loop has not run end to end.',
  },
  authored_mechanism: {
    label: 'Defined in the code',
    note: 'The graph as it is written in the repository today.',
  },
  measured_execution: {
    label: 'Measured run',
    note: 'What actually ran, read from saved results.',
  },
  verified_preparation: {
    label: 'Checked preparation',
    note: 'The inputs were loaded and the first request was prepared. No model output exists.',
  },
  research_proposal: {
    label: 'Not yet built',
    note: 'An extension that has not been implemented or tested.',
  },
};

export const SECTION_LABEL: Record<string, string> = {
  idea: 'Section 1, Evaluation protocol',
  lab: 'Section 2, The executable graph',
  oracle: 'Section 2, Figure 3',
  trace: 'Section 2, Failure diagnosis',
  research: 'Section 3, Context-conditioned prompts',
  results: 'Section 4, Execution study and limitations',
};

export const HERO = {
  lede: 'Zenith studies whether recurring failures in a multi-stage language-model program can guide useful revisions.',
  question:
    'The program reads market data saved at a cutoff, records a forecast, and compares that forecast with observations made later. This site follows the paper section by section. Each node of the executable graph can be opened to show its instruction, its declared inputs and its expected output.',
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
  const edition =
    f.real.length > 0 && f.synthetic.length > 0
      ? ` In this demonstration the ${list(f.real)} feeds contain real saved data and the ${list(f.synthetic)} feeds contain synthetic examples; each feed is labelled in the graph.`
      : '';
  return [
    `The Lab has ${f.total} nodes: ${numberWord(f.feeds)} data feeds and ${f.reasoning} reasoning steps. ${capital(numberWord(f.acquired.length))} feeds are acquired (${list(f.acquired)}), and a calculator derives regime summaries from the stock, ETF and macro feeds.${edition}`,
    `${capital(numberWord(f.miners))} miners, one for each feed, each extract the main signals from their feed. The first synthesis maps where their findings agree and conflict, Orient builds causal hypotheses, and Decide freezes a thesis as checkpoint CP1. A second, directed pass re-reads every feed for that thesis before the Director freezes predictions at CP2. Integrity then audits both passes.`,
    CHAPTER_COPY.lab.paragraphs[2],
  ];
}

export const CHAPTER_COPY: Record<string, { kicker: string; paragraphs: string[] }> = {
  idea: {
    kicker: 'The loop',
    paragraphs: [
      'Zenith runs in rounds. The Lab reads feeds saved at a cutoff and freezes its forecast. Later feeds arrive. Oracle compares the frozen forecast with them and records a hypothesis about what went wrong. Evolve turns that hypothesis into one concrete change to an instruction, an input or a dependency.',
      'A change is accepted only if it improves results on inputs that were not used to choose it. The original and revised graphs therefore run again on another window, with the base model held fixed and the score declared before the outcomes are seen.',
      'The cutoff separates what the Lab may read from what is later used to judge it. Nothing from after the cutoff may reach the Lab’s inputs. Research done after the outcome can explain an event, but it cannot become evidence the earlier run had.',
    ],
  },
  lab: {
    kicker: 'Read earlier evidence',
    paragraphs: [
      'The Lab reads saved data feeds through a graph of reasoning steps. A calculator derives regime summaries from the stock, ETF and macro feeds.',
      'One miner reads each feed. The first synthesis maps where their findings agree and conflict, Orient builds causal hypotheses, and Decide freezes a thesis as checkpoint CP1. A second, directed pass re-reads every feed for that thesis before the Director freezes predictions at CP2. Integrity then audits both passes.',
      'Every node saves its output, so a reviewer can find the step where an unsupported claim first appeared and see what that step was given. Selecting a node shows its instruction, its declared inputs and the output it must produce.',
    ],
  },
  oracle: {
    kicker: 'Compare with later evidence',
    paragraphs: [
      'Oracle receives two things: the frozen Lab record with the feeds it saw, and the same sources captured after the cutoff. Tools compute numeric before-and-after differences without a model. One review per data source describes what that source shows later.',
      'An evidence summary combines those findings, and a failure hypothesis maps them back onto the Lab’s own evidence. That attribution is a hypothesis about a failure. It does not identify a cause.',
    ],
  },
  evolve: {
    kicker: 'Propose one change',
    paragraphs: [
      'Evolve reads Oracle’s report and drafts one revision: which part of a node’s instruction file to change and how. A version step records the change so the original and the revision can both be run again.',
      'A proposed change is a hypothesis. Showing that it helps takes a separate comparison on later cases, with a score fixed in advance, counting regressions as well as gains.',
    ],
  },
  results: {
    kicker: 'What actually ran',
    paragraphs: [
      'The full loop has not run end to end yet. What did run is the Lab, on original saved feeds from several dates, with the graph, policy, model and response limit held fixed.',
      'The numbers below are read from the published receipts. Valid JSON from one node is an execution result. It says nothing yet about forecast accuracy.',
    ],
  },
  'results:verified_preparation': {
    kicker: 'What has been prepared',
    paragraphs: [
      'This demonstration runs the graph on mixed inputs. The stock, ETF and prediction-market inputs are real saved data, the macro and news inputs are synthetic examples, and the calculator summaries are recomputed from both. The real data are withheld from this site while their permissions are reviewed; the synthetic examples are published in full.',
      'The checked result is limited to preparation. The Lab loads every input and prepares the request for its first reasoning step, then stops before any model call. No forecast, Oracle diagnosis or Evolve comparison has been produced in this configuration.',
    ],
  },
  next: {
    kicker: 'What still needs testing',
    paragraphs: [
      'Each reasoning node would keep a fixed job, the same inputs and the same output contract. A small neural controller would read context available at the cutoff, such as VIX and sentiment, and select slightly different wording for how a node interprets its evidence.',
      'The controller’s outputs are prompt settings: numbers between 0 and 1 that index a versioned catalogue of written variants. The exact rendered prompt is saved with every run. Backpropagation could train the controller from measured losses, but no derivative flows through the language model or the text choice.',
      'None of this has been implemented. The controller would be fitted on development cases, frozen, then tested on later cases, including regime changes and regressions.',
    ],
  },
};

export const LOOP_STAGES = [
  {
    id: 'feeds',
    side: 'before',
    title: 'Earlier evidence',
    detail: 'Feeds saved at the cutoff',
    receives: 'The acquired feeds and the calculator, exactly as saved at time t.',
    produces: 'A fixed input universe. Anything absent here was unavailable to the run.',
  },
  {
    id: 'lab',
    side: 'before',
    title: 'Lab',
    detail: 'Multi-step reasoning graph',
    receives: 'Only the saved feeds and its own earlier outputs.',
    produces: 'A saved output at every node, a thesis at CP1 and predictions at CP2.',
  },
  {
    id: 'frozen',
    side: 'boundary',
    title: 'Frozen prediction',
    detail: 'Sealed before outcome',
    receives: 'The Lab’s CP1 and CP2 records.',
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
    produces: 'Numeric differences, one review per data source and a failure hypothesis.',
  },
  {
    id: 'evolve',
    side: 'after',
    title: 'Evolve',
    detail: 'Propose one change',
    receives: 'Oracle’s report.',
    produces: 'One revision to an instruction, input or dependency, recorded as a new version.',
  },
  {
    id: 'compare',
    side: 'test',
    title: 'Compare on another window',
    detail: 'Original and revision, same later inputs',
    receives: 'Both versions and later cases nobody used to choose the revision.',
    produces: 'Gains and regressions under a score fixed in advance. Not yet run end to end.',
  },
] as const;

export const DIAGNOSIS_ROWS = [
  ['Evidence unavailable', 'Was the relevant information absent from the saved input universe?'],
  ['Evidence not supplied', 'Was it in that universe but missing from the node’s actual input?'],
  ['Reasoning error', 'Did the node receive the evidence but draw an unsupported conclusion?'],
  ['Execution failure', 'Did truncation, parsing or another runtime error prevent a usable output?'],
] as const;
