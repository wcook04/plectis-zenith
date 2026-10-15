// Teaching copy for each chapter served by /api/v1/site. The wording follows
// paper/zenith.tex; measured numbers are never written here. They are read
// from the public receipts at runtime.

export const EVIDENCE_KIND_LABEL: Record<string, { label: string; note: string }> = {
  proposed_process: {
    label: 'Proposed procedure',
    note: 'A procedure we propose to build. This section does not report a completed experiment.',
  },
  authored_mechanism: {
    label: 'Defined in the code',
    note: 'The source code describes this procedure. Its results must be established by a separate experiment.',
  },
  measured_experiment: { label: 'Recorded experiment', note: 'Saved inputs and outputs show what the program did. Compare the results below to see whether a change helped.' },
  measured_execution: {
    label: 'Recorded execution',
    note: 'What actually ran, read from saved results.',
  },
  verified_preparation: {
    label: 'Inputs and request prepared',
    note: 'The inputs were loaded and the first request was prepared. No model output exists.',
  },
  research_proposal: {
    label: 'Research question',
    note: 'An experiment we have not yet completed, or a result we have not yet established.',
  },
};

export const SECTION_LABEL: Record<string, string> = {
  idea: 'The research question', lab: 'The native observation task',
  oracle: 'Measured repair', trace: 'Frozen prediction programs',
  research: 'Interpretation and next evidence', results: 'Measured comparisons',
};

export const HERO = {
  lede: 'Can an AI learn better ways to find faults in software?',
  question: 'Zenith asks an AI model to write tests, runs those tests on software, and gives the results back to the model so it can repair code. We then test whether anything it learned helps with a later program.',
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
  const edition = ' This earlier demonstration uses invented observations of a toy system called System A. It does not use measurements from a real physical system.';
  return [
    `The diagram has ${f.total} boxes, called nodes: ${numberWord(f.feeds)} supply saved data and ${f.reasoning} describe reasoning steps. ${capital(numberWord(f.acquired.length))} data sources contain observations (${list(f.acquired)}). Another step calculates summaries from those same observations.${edition}`,
    `${capital(numberWord(f.miners))} steps called miners each read one data source. Synthesis compares their findings. Orient proposes possible causes, and Decide saves one explanation at checkpoint CP1. The miners read the data again to examine that explanation. Director saves predictions at checkpoint CP2, and Integrity reviews the reasoning. These names identify steps in a program; they do not establish that its explanations or predictions are correct.`,
    CHAPTER_COPY.lab.paragraphs[0],
  ];
}

export const CHAPTER_COPY: Record<string, { kicker: string; paragraphs: string[] }> = {
  idea: { kicker: 'Learn from a program’s wrong answers', paragraphs: [
    'When a program gives the wrong answer, the test that exposed the error can help us decide how to change it. This earlier study saved proposed programs, failed examples and the observations used to make predictions.',
    'The study asks what a counter reported by the SQLite database actually counts. It can include changes that were later undone, or extra writes, even when the number of saved items does not change.',
  ] },
  lab: { kicker: 'Run tests on the reference software', paragraphs: [
    'The model proposes sequences of database operations. Zenith runs each sequence in a disposable SQLite database. It records the reported counter, the number of saved items and the sum of their values.',
    'Each method receives the same earlier tests and answers. The model writes Python code to predict the answers for other sequences. Zenith runs that code with limits on its operations and resources, and saves any execution errors.',
  ] },
  oracle: { kicker: 'Compare predictions with actual answers', paragraphs: [
    'Zenith compares a proposed program’s predictions with the database’s actual responses. If the program is rejected, the next request to the model includes that code and its errors.',
    'During development, a valid change may be retained even if its score is unchanged; worse results are also recorded. Additional combinations of operations are tested only after the model has finished writing code. The conclusions apply to the particular database implementations selected for this study.',
  ] },
  evolve: { kicker: 'Save each version before testing it', paragraphs: [
    'The comparison gives the model different histories: the latest proposed program, all earlier attempts, or only the final collected observations. Each method has the same limit on proposals and can use the same operations.',
    'Zenith saves each version before trying the later test inputs. It also tests the first version, the final version without the earlier observations, and a program that has not learned from those observations. These comparisons ask whether the revisions and the supplied history actually helped.',
  ] },
  results: { kicker: 'Read the recorded results', paragraphs: [
    'The table shows the initial comparison against the reference software. The linked later experiments ask whether rewriting from scratch, keeping several proposed programs or collecting more observations helps.',
    'The saved records include correct answers, unsupported predictions and execution errors. Repeating the experiment with different settings of the same software does not establish that the method works in unrelated applications.',
  ] },
  'results:verified_preparation': { kicker: 'Historical fixture preparation', paragraphs: [
    'System A is a toy example with invented observations. Zenith loaded its data and prepared a request, but did not send the request to a model. No prediction result was produced.',
  ] },
  next: { kicker: 'Test software from other sources', paragraphs: [
    'A later experiment should test independently written software, including programs that look similar but behave differently. The results here do not show that Zenith can discover the meaning of arbitrary software or save money over a long period.',
    'Count the work needed to collect observations, execute programs and request AI responses. Keep unsuccessful attempts in the comparison, and leave unanswered questions open.',
  ] },
};

export const LOOP_STAGES = [
  {
    id: 'feeds',
    side: 'before',
    title: 'Earlier evidence',
    detail: 'Saved input data',
    receives: 'The source observations and derived summaries, exactly as saved at time t.',
    produces: 'The data the program is allowed to read. It cannot use observations collected later.',
  },
  {
    id: 'lab',
    side: 'before',
    title: 'Lab',
    detail: 'Read data; predict',
    receives: 'Only the saved feeds and its own earlier outputs.',
    produces: 'A saved list of actions, measured numbers and predictions that cannot be changed after the outcome is revealed.',
  },
  {
    id: 'frozen',
    side: 'boundary',
    title: 'Frozen prediction',
    detail: 'Saved before outcome',
    receives: 'The predictions produced by the Lab steps.',
    produces: 'A record nobody may edit after later evidence is revealed.',
  },
  {
    id: 'later',
    side: 'after',
    title: 'Later evidence',
    detail: 'Later observations',
    receives: 'New observations from the same sources, collected after the time being predicted.',
    produces: 'What actually happened, for comparison only.',
  },
  {
    id: 'oracle',
    side: 'after',
    title: 'Oracle',
    detail: 'Compare and diagnose',
    receives: 'The frozen record, the feeds the Lab saw, and the later feeds.',
    produces: 'A proposed explanation for a prediction error, with the observations it relies on and an alternative explanation.',
  },
  {
    id: 'evolve',
    side: 'after',
    title: 'Evolve',
    detail: 'Propose one change',
    receives: 'Oracle’s report.',
    produces: 'A proposed change to one instruction, saved as a new version for comparison.',
  },
  {
    id: 'compare',
    side: 'test',
    title: 'Try later observations',
    detail: 'Original and revision, same later inputs',
    receives: 'Both versions and later cases nobody used to choose the revision.',
    produces: 'Scores for both versions under the same rule, chosen before the test. The proposal itself does not establish an improvement.',
  },
] as const;

export const DIAGNOSIS_ROWS = [
  ['Evidence unavailable', 'Was the relevant information missing from all the saved inputs?'],
  ['Evidence not supplied', 'Was the information saved, but omitted from the request this step received?'],
  ['Reasoning error', 'Did the node receive the evidence but draw an unsupported conclusion?'],
  ['Execution failure', 'Did truncation, parsing or another runtime error prevent a usable output?'],
] as const;
