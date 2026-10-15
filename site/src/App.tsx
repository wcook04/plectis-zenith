import { useEffect, useMemo, useRef, useState } from 'react';
import { api, apiUrl, type Chapter, type Doc, type Evidence, type Graph, type Paper, type Site } from './api';
import { CHAPTER_COPY, DIAGNOSIS_ROWS, EVIDENCE_KIND_LABEL, HERO, labParagraphs, type GraphFacts } from './content/copy';
import { laneIndex, laneName } from './lib/lanes';
import { GraphExplorer } from './components/graph/GraphExplorer';
import { LoopDiagram } from './components/LoopDiagram';
import { Markdown } from './components/Markdown';
import { PaperAside, linkLabel } from './components/PaperAside';
import { MechanismDiagram, SettingsIllustration } from './components/Research';
import { Results } from './components/Results';
import { RunPicker, type RunChoice } from './components/RunPicker';
import type { RunContext } from './components/Inspector';
import { latexToText } from './lib/latex';
import { SiteEvidenceContext, SiteFiguresContext } from './lib/siteContext';
import { Preparation, preparationSummary } from './components/Preparation';
import { nodeName } from './lib/naming';
import { useAsync } from './lib/hooks';
import { ThemeToggle } from './components/ThemeToggle';
import { CopyButton } from './components/CopyButton';

const RECEIPT_LABEL: Record<string, string> = {
  'progress-campaign': 'Current repair experiment and comparisons with ordinary tests',
  'client-investigation': 'Separate SQLite client investigation pilot',
  'client-investigation-v2': 'SQLite client pilot v2, reasoning none',
  'client-investigation-v2-low': 'SQLite client pilot v2, reasoning low',
  'advance-campaign': 'Earlier Advance repair and memory experiments',
  'decomposition-result': 'Earlier program-restructuring and rule-learning experiments',
  'observation-learning-result': 'Earlier experiment learning to predict software responses',
  'observation-screens': 'Follow-on repair, candidate search and composition tests',
  'investigation-learning-result': 'Earlier software-testing experiments',
  sources: 'Where each input comes from, with file hashes',
  replacements: 'Synthetic multi-feed observations',
  'demo-result': 'Preparation record',
  observations: 'Synthetic observations',
  'window-result': 'Window experiment record',
  'conditional-result': 'Conditional continuation record',
};

const PROGRESS_COPY: Record<string, string[]> = {
  idea: ['An AI can suggest a repair to a faulty program. Zenith asks a further question: can the AI learn a way to test programs that is useful again, when it encounters another problem?',
    'We save the code it writes, the tests it chooses, and the software’s actual responses. Later experiments compare that saved code with ordinary reusable code and tests chosen in advance. Some repairs work, and some tests can be reused. So far, the learned testing methods have not beaten those simpler alternatives.'],
  oracle: ['Zenith gives a language model a program to repair and a description of what it should do. The model proposes inputs to try. Zenith runs those inputs through the proposed program and the reference software, whose actual behavior supplies the expected answer. It sends any disagreement and the code back to the model for repair.',
    'Zenith accepts a proposed repair only if it still answers every previously correct measured example correctly. It then stops changing that version and tries additional examples that were not used to choose the repair. Passing these examples shows agreement on those particular inputs; it does not prove the program works for every possible input.',
    'A separate experiment asks the model to write a tester: a program that chooses tests for other software. Zenith saves the tester unchanged before trying it on later database programs. In the older diagrams, Lab names the steps that investigate, Oracle the steps that compare results, and Evolve the steps that propose a change.'],
  results: ['The experiments below ask three different questions: can a saved tester find faults in later programs, can new tests help the model repair code, and can a learner retain the information it needs to predict later behavior? Each has its own comparison and limits.'],
  next: ['We need to test software obtained independently of this project, with faults that a competent set of ordinary tests does not already find. The learned tester must be saved before it sees that software, so the later answers cannot influence its design.',
    'A useful result would be a tester that chooses better inputs because of earlier experience: it finds more faults, or needs fewer attempts, than ordinary reusable tests. The comparison must include the cost of learning the tester. We have not yet demonstrated this advantage.'],
};

const CURRENT_TITLES: Record<string, string> = {
  idea: 'The research question', oracle: 'How it works', results: 'What we found', next: 'What we still need to test',
};

// Keep the API's six chapter IDs and old deep links, but give the current
// programme one shorter reading path. Historical profiles keep their layout.
function readingSite(site: Site): Site {
  if (site.active_evidence_id !== 'progress-campaign') return site;
  return { ...site, chapters: site.chapters.filter(c => c.id !== 'lab' && c.id !== 'evolve')
    .map(c => ({ ...c, title: CURRENT_TITLES[c.id] ?? c.title })) };
}

// Older site metadata still names Advance as active. Keep its reading path
// available without using that receipt as the current Progress result.
const ADVANCE_COPY: Record<string, string[]> = {
  idea: ['These earlier experiments ask whether code learned during one task helps with a later task. We compare the answers the programs produce and the amount of testing they require.'],
  lab: ['The AI writes programs that choose inputs to try on reference software. Zenith limits the permitted operations and records the software’s answers, requests that break those rules, and requests that could not be delivered.'],
  oracle: ['Zenith sends the test results and the failed program back to the AI for repair. A proposed repair must preserve every previously correct measured answer. Zenith then saves that version unchanged and tests it on additional inputs.'],
  evolve: ['A separate learner tries to predict software responses after a sequence of actions. We test whether it remembers enough to continue the sequence or try a different action from the same point. Programs written by the researchers remain separate from programs learned by the AI.'],
  results: ['The saved Advance results distinguish software-repair experiments from experiments about memory. Requests to the AI and their reported costs are totalled, but scores from different experiments are reported separately.'],
  next: ['We still need to show that learned code helps on other tasks, works when combined with other learned code, or improves the method that does the learning. Comparisons with ordinary reusable code remain necessary.'],
};

function activeEvidenceUrl(site: Site, chapter?: Chapter): string | undefined {
  return site.active_evidence_id ? site.evidence[site.active_evidence_id] : chapter?.evidence_urls[0];
}

const FIGURE_LABEL: Record<string, string> = {
  replay: 'The full loop',
  lab: 'Lab overview',
  oracle: 'Oracle overview',
  evolve: 'Evolve overview',
  'lab-detail': 'Lab, every node',
  'oracle-detail': 'Oracle, every node',
  'evolve-detail': 'Evolve, every node',
};

// Each chapter's figure gets the track its content needs.
const FIGURE_TRACK: Record<string, string> = {
  idea: 'wide',
  lab: 'full',
  oracle: 'full',
  evolve: 'compact',
  results: 'wide',
  next: 'wide',
};

const NAV_LABEL: Record<string, string> = {
  idea: 'The idea',
  lab: 'Lab',
  oracle: 'Oracle',
  evolve: 'Evolve',
  results: 'What ran',
  next: 'Next',
};

export default function App() {
  const site = useAsync(() => api.site(), []);
  const paper = useAsync(() => api.paper(), []);

  if (site.status === 'loading') {
    return (
      <Shell>
        <p className="page-status" role="status">Loading the research…</p>
      </Shell>
    );
  }
  if (site.status === 'error') {
    return (
      <Shell>
        <div className="page-status" role="alert">
          <h1>The research data could not be loaded</h1>
          <p>
            The website could not read its published data ({site.message}). You can read the
            <a href="https://github.com/wcook04/plectis-zenith/blob/main/docs/status.md"> saved results on GitHub</a>.
            If you are running the website on your own computer, start its data server from the repository
            directory with <code>python -m zenith serve --port 4175</code> and reload.
          </p>
        </div>
      </Shell>
    );
  }
  return <Page site={readingSite(site.value)} paper={paper.status === 'ready' ? paper.value : null} />;
}

function useCurrentChapter(ids: string[]): string | null {
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    if (ids.length === 0 || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setCurrent(visible[0].target.id);
      },
      { rootMargin: '-120px 0px -60% 0px' },
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [ids.join('|')]); // eslint-disable-line react-hooks/exhaustive-deps
  return current;
}

function Shell({ children, site }: { children: React.ReactNode; site?: Site }) {
  const [noticeOpen, setNoticeOpen] = useState(false);
  const current = useCurrentChapter(site ? [...site.chapters.map((c) => c.id), 'paper'] : []);
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <div className="notice-bar">
          <div className="wrap notice-bar__inner">
            <p>
              <strong>{site?.notice ?? 'Experimental research prototype.'}</strong>
              <span className="notice-bar__extra"> Tests on software examples written for this research.</span>
            </p>
            <button type="button" className="z-link-button" onClick={() => setNoticeOpen(true)}>
              Research notice
            </button>
          </div>
        </div>
        <div className="wrap masthead__inner">
          <a className="wordmark" href="#top" translate="no">
            Zenith
          </a>
          {site && (
            <nav aria-label="Chapters" className="nav">
              {site.chapters.map((chapter) => (
                <a key={chapter.id} href={`#${chapter.id}`} aria-current={current === chapter.id ? 'true' : undefined}>
                  {site.active_evidence_id === 'progress-campaign' ? chapter.title
                    : chapter.evidence_kind === 'verified_preparation' ? 'Preparation' : (NAV_LABEL[chapter.id] ?? chapter.title)}
                </a>
              ))}
              <a href="#paper" aria-current={current === 'paper' ? 'true' : undefined}>
                Paper
              </a>
            </nav>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {children}
      </main>
      {noticeOpen && <NoticeDialog url={site?.notice_url ?? '/api/v1/documents/notice'} onClose={() => setNoticeOpen(false)} />}
    </>
  );
}

function NoticeDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const doc = useAsync(() => api.document(url), [url]);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal?.();
  }, []);
  return (
    <dialog ref={ref} className="notice-dialog" onClose={onClose} aria-label="Research notice">
      <div className="notice-dialog__body">
        {doc.status === 'ready' ? (
          <Markdown source={doc.value.content} base={doc.value.base_url} />
        ) : doc.status === 'error' ? (
          <p>The notice could not be loaded. Experimental research prototype.</p>
        ) : (
          <p role="status">Loading…</p>
        )}
      </div>
      <form method="dialog" className="notice-dialog__foot">
        <button type="submit" className="button">
          Close
        </button>
      </form>
    </dialog>
  );
}

function useGraph(url: string | null) {
  return useAsync<Graph | null>(() => (url ? api.graph(url) : Promise.resolve(null)), [url]);
}

function Page({ site, paper }: { site: Site; paper: Paper | null }) {
  const byId = useMemo(() => new Map(site.chapters.map((c) => [c.id, c])), [site]);
  const progressActive = site.active_evidence_id === 'progress-campaign';
  const advanceActive = site.active_evidence_id === 'advance-campaign';
  const learningActive = Boolean(site.active_evidence_id
    || site.evidence['observation-learning-result'] || site.evidence['investigation-learning-result']);
  const lab = useGraph(byId.get('lab')?.graph_url ?? null);
  const deepLink = useMemo(() => new URLSearchParams(window.location.search).get('node'), []);
  const byline = useByline(site);
  const latex = usePaperLatex(site);

  return (
    <SiteEvidenceContext.Provider value={site.evidence}>
    <SiteFiguresContext.Provider value={site.figures}>
    <Shell site={site}>
      <section className="hero wrap" id="top" aria-labelledby="title">
        <div className="hero__main">
        <h1 id="title">{titleParts(site.title)}</h1>
        <p className="hero__lede">{HERO.lede}</p>
        <p className="hero__question">{HERO.question}</p>
        <div className="hero__actions">
          <a className="button" href={apiUrl(paper?.source.url ?? site.documents.paper ?? '/api/v1/documents/paper')} target="_blank" rel="noreferrer">
            Current paper source
          </a>
          <a className="button button--ghost" href={progressActive ? '#results' : '#lab'}>
            {progressActive ? 'Read the findings' : 'Explore the investigation'}
          </a>
          {byline && <span className="hero__byline">{byline}</span>}
        </div>
        </div>
        <nav className="hero__map" aria-labelledby="contents-caption">
          <table>
            <caption id="contents-caption">{progressActive ? 'On this page' : 'Contents and the status of the material in each section'}</caption>
            {!progressActive && <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">Number</span>
                </th>
                <th scope="col">Section</th>
                <th scope="col">Status</th>
              </tr>
            </thead>}
            <tbody>
              {site.chapters.map((chapter, i) => (
                <tr key={chapter.id} className={`map-row map-row--${chapter.evidence_kind}`}>
                  {!progressActive && <td className="map-row__num">{i + 1}</td>}
                  <th scope="row" className="map-row__title">
                    <a href={`#${chapter.id}`}>{chapter.title}</a>
                  </th>
                  {!progressActive && <td className="map-row__kind">{EVIDENCE_KIND_LABEL[chapter.evidence_kind]?.label ?? chapter.evidence_kind}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </nav>
      </section>
      <StatusStrip site={site} />

      {site.chapters.map((chapter, index) => (
        <ChapterSection
          key={chapter.id}
          chapter={chapter}
          index={index}
          paper={paper}
          latex={latex}
          concise={progressActive}
          paragraphs={
            progressActive ? PROGRESS_COPY[chapter.id] : advanceActive ? ADVANCE_COPY[chapter.id] : chapter.id === 'lab' && !learningActive
              ? labParagraphs(lab.status === 'ready' && lab.value ? graphFacts(lab.value) : null)
              : CHAPTER_COPY[`${chapter.id}:${chapter.evidence_kind}`]?.paragraphs
          }
        >
          {chapter.id === 'idea' && !learningActive && <><LoopDiagram /><ApplicationExample /></>}
          {chapter.id === 'lab' && !learningActive && (
            <LabFigure site={site} graph={lab.status === 'ready' ? lab.value : null} deepLink={deepLink} />
          )}
          {chapter.id === 'oracle' && !learningActive && <OracleFigure chapter={chapter} />}
          {chapter.id === 'evolve' && !learningActive && <EvolveFigure chapter={chapter} />}
          {chapter.id === 'results' && (
            <>{progressActive && <ClientStudy site={site} />}
              <ResultsFigure chapter={chapter} labGraph={lab.status === 'ready' ? lab.value : null} site={site} /></>
          )}
          {chapter.id === 'next' && !learningActive && <NextFigure chapter={chapter} />}
          {chapter.id === 'next' && progressActive && <div className="chapter__text">
            <h3>Improving future improvement</h3>
            <p>The longer-term question is whether experience improves the procedure that makes future improvements. We would compare an original and revised improver on the same untouched starting programs and fresh task families, then test whether the successor helps produce a better next generation. The complete cost and failed attempts belong in that comparison. This has not been demonstrated.</p>
            <p>The <a href="https://github.com/wcook04/plectis-erdos">Plectis mathematical corpus</a> supplies proofs, partial results and open obligations; <a href="https://github.com/wcook04/plectis-atlas">Plectis Atlas</a> helps readers inspect OpenAI’s mathematics release and attributed outside assessments. These could support experiments on which argument or check to try next. They are not yet a learning integration with Zenith. Lean checks a supplied proof; failed search does not establish that a statement is false.</p>
            <p>I’m building Zenith with AI coding agents and learning the research methods as I go, with limited experience in this area. This is my current understanding. Collaboration, corrections and guidance on prior work, fair comparisons and useful tasks are welcome through <a href="https://github.com/wcook04/plectis-zenith/issues">project issues</a>. The <a href="https://github.com/wcook04/plectis-zenith#what-we-want-to-find-out">README explains these possible directions and their precedents</a>.</p>
          </div>}
        </ChapterSection>
      ))}

      <PaperSection site={site} paper={paper} />
      <footer className="footer">
        <div className="wrap footer__inner">
          <p>
            <strong>Experimental research prototype.</strong> Each result describes the particular programs and inputs tested.
            These experiments do not establish that Zenith can reliably test or repair other software. Earlier studies are labelled separately.
          </p>
          <p>
            <a href="https://github.com/wcook04/plectis-zenith" target="_blank" rel="noreferrer">
              Source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </Shell>
    </SiteFiguresContext.Provider>
    </SiteEvidenceContext.Provider>
  );
}

function ApplicationExample() {
  const views = [
    ['Measurements', 'Air temperature and humidity'],
    ['Subsystems', 'Soil moisture and fan readings'],
    ['Environment', 'Weather observations and forecasts available at the cutoff'],
    ['Events', 'Door openings and sensor outage reports'],
    ['Interventions', 'Planned and executed irrigation or ventilation'],
    ['Derived summaries', 'Trends calculated from those same readings'],
  ];
  return (
    <section className="application-example" aria-labelledby="application-example-title">
      <div>
        <p className="paper-aside__head">A possible application</p>
        <h3 id="application-example-title">What will a greenhouse be like in six hours?</h3>
        <p>Freeze the information available at noon. Predict the air temperature and humidity at 6 pm, with units and uncertainty. Later, compare those predictions with the readings.</p>
        <p>The reasoning has to connect these views: a missing sensor reading is not evidence of stable conditions, two summaries of one weather report are not independent confirmation, and scheduled irrigation has not necessarily happened.</p>
        <p>In physics, this is a problem of predicting an evolving state from partial observations. The graph would organise the measurements, conditions and competing explanations, using an appropriate physical model or numerical solver where available. Sensor history can matter: a single position measurement does not tell us which way something is moving. <a href="https://underactuated.mit.edu/output_feedback.html" target="_blank" rel="noreferrer">Background: partial observations and state estimation.</a></p>
        <p>A useful study would compare the graph with a simple forecast and an appropriate numerical model. This is a motivating example; the published System A data are a separate abstract toy, not a greenhouse simulation.</p>
      </div>
      <div>
        <table>
          <caption>Different perspectives on one greenhouse</caption>
          <thead><tr><th scope="col">Feed role</th><th scope="col">Possible observations</th></tr></thead>
          <tbody>{views.map(([role, observations]) => <tr key={role}><th scope="row">{role}</th><td>{observations}</td></tr>)}</tbody>
        </table>
        <p className="application-example__other"><strong>Heat flow:</strong> temperature probes, heater power, ambient conditions and vent logs could support a forecast of a chamber’s temperature six hours later. <a href="https://openstax.org/books/university-physics-volume-2/pages/1-6-mechanisms-of-heat-transfer" target="_blank" rel="noreferrer">Heat-transfer background.</a></p>
        <p className="application-example__other"><strong>Vibration:</strong> camera positions, accelerometer readings, applied-force history and calibration records could support a forecast of a vibrating mass’s displacement one second later. <a href="https://openstax.org/books/university-physics-volume-1/pages/15-5-damped-oscillations" target="_blank" rel="noreferrer">Damped-oscillation background.</a></p>
        <p className="application-example__other"><strong>Transport:</strong> concentration sensors, flow measurements, geometry and valve logs could support a forecast of concentration at a downstream sensor. The model would need the relevant initial and boundary conditions.</p>
        <p className="application-example__other">These are proposed uses. No physical solver is connected or evaluated in this demonstration. The reasoning graph records computational dependencies; its arrows are not claims about physical causation. Physical feedback belongs in the system model.</p>
        <p className="application-example__other">Finance is another possible application, with its own data and evaluation requirements. This research is not financial advice.</p>
      </div>
    </section>
  );
}

// One line under the hero with where the work actually stands, read from the
// receipt bound to the results chapter.
function StatusStrip({ site }: { site: Site }) {
  const chapter = site.chapters.find((c) => c.id === 'results')
    ?? site.chapters.find((c) => c.evidence_kind === 'measured_experiment' || c.evidence_kind === 'measured_execution' || c.evidence_kind === 'verified_preparation');
  const url = activeEvidenceUrl(site, chapter);
  const evidence = useAsync<Evidence | null>(() => (url ? api.evidence(url) : Promise.resolve(null)), [url]);
  const progressActive = site.active_evidence_id === 'progress-campaign';
  const advanceActive = site.active_evidence_id === 'advance-campaign';
  const observationActive = site.active_evidence_id === 'observation-learning-result';
  const sourcesUrl = site.active_evidence_id || site.evidence['investigation-learning-result'] ? undefined : site.evidence.sources;
  const sources = useAsync<Evidence | null>(() => (sourcesUrl ? api.evidence(sourcesUrl) : Promise.resolve(null)), [sourcesUrl]);
  const composition = sources.status === 'ready' && sources.value ? compositionSentence(sources.value) : null;
  let summary: string | null = null;
  if (evidence.status === 'ready' && evidence.value) {
    const schema = String(evidence.value.data.schema ?? '');
    if (schema === 'zenith_progress_campaign_report_v1' && validProgressReceipt(evidence.value.data)) {
      const data = evidence.value.data;
      summary = data.conformance_studies.length
        ? `Current repair experiments: ${progressStatusLabel(data.status)}; ${data.conformance_studies.length} ${data.conformance_studies.length === 1 ? 'study' : 'studies'} published.`
        : 'Current Progress campaign results pending.';
    }
    else if (schema === 'zenith_advance_campaign_v1' && validAdvanceReceipt(evidence.value.data)) {
      const data = evidence.value.data;
      summary = `${data.status === 'complete' ? 'Advance campaign analysis complete' : 'Advance campaign analysis pending'}; ${data.total_calls} recorded call attempts; $${Number(data.total_reported_cost_usd).toFixed(4)} reported cost.`;
    }
    else if (schema.startsWith('zenith_demo_preparation')) summary = preparationSummary(evidence.value);
    else if (schema.startsWith('zenith_original_feed_window')) summary = windowSummary(evidence.value);
    else if (schema === 'zenith_learning_evidence_v1') summary = `${evidence.value.data.total_calls} model calls; $${Number(evidence.value.data.total_reported_cost_usd).toFixed(4)} reported cost across all recorded attempts.`;
    else if (schema === 'zenith_observation_learning_evidence_v1') {
      const data = evidence.value.data as unknown as ObservationReceipt;
      summary = `Earlier software-prediction comparison: ${observationStatus(data)}; ${data.total_calls} requests to the AI including connection tests; $${Number(data.total_reported_cost_usd).toFixed(4)} reported cost.`;
    }
  }
  if (progressActive && !url) summary = 'Current Progress campaign results pending.';
  else if (progressActive && evidence.status === 'error') summary = 'The current experiment result file could not be loaded.';
  else if (progressActive && evidence.status === 'ready' && (!evidence.value || !validProgressReceipt(evidence.value.data))) summary = 'The current experiment result file uses an unsupported format.';
  else if (advanceActive && !url) summary = 'Advance campaign results pending.';
  else if (advanceActive && evidence.status === 'error') summary = 'The earlier Advance experiment result file could not be loaded.';
  else if (advanceActive && evidence.status === 'ready' && (!evidence.value || !validAdvanceReceipt(evidence.value.data))) summary = 'The earlier Advance experiment result file uses an unsupported format.';
  else if (observationActive && !url) summary = 'Observation study results pending.';
  else if (observationActive && evidence.status === 'error') summary = 'The observation experiment result file could not be loaded.';
  else if (observationActive && evidence.status === 'ready' && evidence.value
    && evidence.value.data.schema !== 'zenith_observation_learning_evidence_v1') summary = 'The observation experiment result file uses an unsupported format.';
  if (!chapter || (progressActive && evidence.status === 'ready' && evidence.value
    && validProgressReceipt(evidence.value.data) && evidence.value.data.status === 'complete')) return null;
  return (
    <section className="status-strip" aria-label="Current status">
      <div className="wrap status-strip__inner">
        <div>
          <p className="status-strip__lead">
            <strong>{summary ?? 'Loading the recorded experiment status…'}</strong>
          </p>
          {(composition ?? site.data_note) && <p className="status-strip__note">{composition ?? site.data_note}</p>}
        </div>
        <a href={`#${chapter.id}`}>{chapter.title}</a>
      </div>
    </section>
  );
}

// One literal sentence on what the inputs are and what this site publishes,
// read from the provenance receipt.
function compositionSentence(sources: Evidence): string | null {
  const snapshots = (sources.data.snapshots as Array<{ lanes?: Array<{ node_id: string; input_origin: string; public_payload?: string }> }>) ?? [];
  const lanes = snapshots[0]?.lanes;
  if (!lanes) return null;
  const name = (id: string) => nodeName(id).replace(/ feed$/, '').toLowerCase().replace('subsystemss', 'SUBSYSTEMS').replace('measurements', 'measurements').replace('interventions', 'intervention');
  const list = (items: string[]) => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`);
  const real = lanes.filter((l) => l.input_origin === 'real_saved_input').map((l) => name(l.node_id));
  const synthetic = lanes.filter((l) => l.input_origin === 'authored_synthetic').map((l) => name(l.node_id));
  const derived = lanes.filter((l) => l.input_origin === 'derived_synthetic_inputs').map((l) => name(l.node_id));
  const parts: string[] = [];
  if (real.length) parts.push(`The ${list(real)} feeds contain real saved data, which this site does not publish.`);
  if (synthetic.length) parts.push(`The ${list(synthetic)} feeds contain synthetic examples written for this demonstration, published here in full.`);
  if (derived.length) parts.push(`The ${list(derived)} feed is computed from the numeric observations.`);
  return parts.join(' ');
}

function windowSummary(evidence: Evidence): string {
  const d = evidence.data as Record<string, unknown>;
  const r = (d.results ?? {}) as Record<string, unknown>;
  const episodes = (r.episodes as unknown[]) ?? [];
  const change = (d.change ?? {}) as { node_id?: string };
  return `${episodes.length} Lab attempts on original saved feeds stopped at ${nodeName(change.node_id ?? '')} when the response ran out of tokens. One instruction change gave valid output on ${Number(r.later_candidate_passes ?? 0)} of ${Number(r.paired_later_episodes ?? 0)} later inputs. No forecast has completed.`;
}

function titleParts(title: string) {
  const [head, ...rest] = title.split(':');
  if (rest.length === 0) return title;
  return (
    <>
      <span className="hero__name" translate="no">{head}</span>
      <span className="hero__sub">{rest.join(':').trim()}</span>
    </>
  );
}

function usePaperLatex(site: Site): string | null {
  const doc = useAsync(() => api.document(site.documents.paper ?? '/api/v1/documents/paper'), [site]);
  return doc.status === 'ready' ? doc.value.content : null;
}

function useByline(site: Site): string | null {
  const doc = useAsync(() => api.document(site.documents.paper ?? '/api/v1/documents/paper'), [site]);
  if (doc.status !== 'ready') return null;
  const match = /\\\\\[4pt\]\s*\n\s*(.+?)\s*\\quad\\textbullet\\quad\s*(.+?)\s*\n/.exec(doc.value.content);
  return match ? `${latexToText(match[1])}, ${latexToText(match[2])}` : null;
}

function graphFacts(graph: Graph): GraphFacts {
  const feeds = graph.nodes.filter((n) => n.group === 'feeds');
  return {
    total: graph.nodes.length,
    feeds: feeds.length,
    acquired: feeds.filter((n) => n.lane !== 'DERIVED').sort((a, b) => laneIndex(a.lane) - laneIndex(b.lane)).map((n) => laneName(n.lane)),
    real: feeds.filter((n) => n.demo_provenance?.input_origin === 'real_saved_input').sort((a, b) => laneIndex(a.lane) - laneIndex(b.lane)).map((n) => laneName(n.lane)),
    synthetic: feeds.filter((n) => n.demo_provenance?.input_origin === 'authored_synthetic').sort((a, b) => laneIndex(a.lane) - laneIndex(b.lane)).map((n) => laneName(n.lane)),
    reasoning: graph.nodes.filter((n) => n.type === 'reasoning').length,
    miners: graph.nodes.filter((n) => /^lab_miner_(?!v2_)/.test(n.id)).length,
  };
}

function ChapterSection({
  chapter,
  index,
  paper,
  latex,
  paragraphs,
  concise = false,
  children,
}: {
  chapter: Chapter;
  index: number;
  paper: Paper | null;
  latex: string | null;
  paragraphs?: string[];
  concise?: boolean;
  children: React.ReactNode;
}) {
  const copy = CHAPTER_COPY[chapter.id];
  return (
    <section className={`chapter chapter--${chapter.id}`} id={chapter.id} aria-labelledby={`${chapter.id}-title`}>
      {concise && chapter.id === 'oracle' && <span id="lab" />}
      <div className="wrap chapter__grid">
        <div className="chapter__text">
          {!concise && <p className={`chapter__status status--${chapter.evidence_kind}`}>
            <span className="chapter__num">{String(index + 1).padStart(2, '0')}</span>
            <span>{EVIDENCE_KIND_LABEL[chapter.evidence_kind]?.label ?? chapter.evidence_kind}</span>
          </p>}
          <h2 id={`${chapter.id}-title`}>{chapter.title}</h2>
          {!concise && EVIDENCE_KIND_LABEL[chapter.evidence_kind] && (
            <p className="chapter__boundary">{EVIDENCE_KIND_LABEL[chapter.evidence_kind].note}</p>
          )}
          {(paragraphs ?? copy?.paragraphs)?.map((p) => <p key={p}>{p}</p>)}
        </div>
        <PaperAside chapter={chapter} paper={paper} latex={latex} />
      </div>
      <div className={`wrap chapter__figure chapter__figure--${FIGURE_TRACK[chapter.id] ?? 'wide'}`}>{children}</div>
      {chapter.document_url && <SourceDocument url={chapter.document_url} />}
    </section>
  );
}

function SourceDocument({ url }: { url: string }) {
  const [open, setOpen] = useState(false);
  const doc = useAsync<Doc | null>(() => (open ? api.document(url) : Promise.resolve(null)), [open, url]);
  return (
    <div className="wrap source-doc">
      <details onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}>
        <summary>Read the detailed method and research notes</summary>
        {doc.status === 'ready' && doc.value && (
          <>
            <p className="source-doc__from">
              From{' '}
              <a href={doc.value.source.url} target="_blank" rel="noreferrer">
                {doc.value.source.path}
              </a>
            </p>
            {doc.value.format === 'markdown' ? (
              <Markdown source={doc.value.content} base={doc.value.base_url} />
            ) : (
              <pre className="z-pre">{doc.value.content}</pre>
            )}
          </>
        )}
        {doc.status === 'loading' && open && <p role="status">Loading…</p>}
        {doc.status === 'error' && <p className="inspector__warn">Could not load the document: {doc.message}</p>}
      </details>
    </div>
  );
}

function Loading({ what }: { what: string }) {
  return (
    <p className="figure-status" role="status">
      Loading {what}…
    </p>
  );
}

function LabFigure({ site, graph, deepLink }: { site: Site; graph: Graph | null; deepLink: string | null }) {
  const [choice, setChoice] = useState<{ value: string; run: RunContext | null }>({ value: 'none', run: null });
  // Keep the open node when the reader switches runs (the explorer remounts
  // so no state from the previous run can linger).
  const [selected, setSelected] = useState<string | null>(deepLink);
  if (!graph) return <Loading what="the Lab graph" />;
  const onChange = (next: RunChoice, value: string) =>
    setChoice({ value, run: next.kind === 'local' ? { kind: 'local', runId: next.summary.run_id, summary: next.summary } : null });
  return (
    <GraphExplorer
      key={choice.value}
      graph={graph}
      title="The Lab graph"
      context={choice.run && choice.run.kind === 'local' ? `Lab graph: saved run ${choice.run.runId}` : 'Lab graph: definitions'}
      initialSelected={selected && graph.nodes.some((n) => n.id === selected) ? selected : null}
      run={choice.run}
      onSelectionChange={(id) => {
        setSelected(id);
        syncNodeParam(id);
      }}
      runControl={
        site.local_runs_enabled ? (
          <RunPicker mission="lab" value={choice.value} onChange={onChange} localEnabled />
        ) : null
      }
    />
  );
}

function syncNodeParam(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set('node', id);
  else url.searchParams.delete('node');
  window.history.replaceState(null, '', url);
}

function OracleFigure({ chapter }: { chapter: Chapter }) {
  const graph = useGraph(chapter.graph_url);
  return (
    <>
      {graph.status === 'ready' && graph.value ? (
        <GraphExplorer graph={graph.value} title="The Oracle graph" context="Oracle graph: definitions" maxHeight={640} />
      ) : graph.status === 'error' ? (
        <p className="inspector__warn">The Oracle graph could not be loaded: {graph.message}</p>
      ) : (
        <Loading what="the Oracle graph" />
      )}
      <div className="diagnosis">
        <h3 className="block-head">Diagnosis starts with what was available</h3>
        <table className="diagnosis__table">
          <thead>
            <tr>
              <th scope="col">Candidate failure</th>
              <th scope="col">Question for the saved record</th>
            </tr>
          </thead>
          <tbody>
            {DIAGNOSIS_ROWS.map(([name, question]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{question}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="block-foot">
          Unresolved cases stay unknown. A repeated failure motivates an intervention test; how often it happens does not
          identify its cause.
        </p>
      </div>
    </>
  );
}

function EvolveFigure({ chapter }: { chapter: Chapter }) {
  const graph = useGraph(chapter.graph_url);
  return (
    <div className="evolve">
      <div className="evolve__graph">
        {graph.status === 'ready' && graph.value ? (
          <GraphExplorer graph={graph.value} title="The Evolve graph" context="Evolve graph: definitions" maxHeight={320} />
        ) : (
          <Loading what="the Evolve graph" />
        )}
      </div>
      <div className="evolve__contrast" aria-label="Proposing compared with demonstrating">
        <div className="contrast contrast--propose">
          <h3>Proposing a revision</h3>
          <p>One changed instruction, input or dependency, saved as a new version.</p>
          <p className="contrast__state">What Evolve produces</p>
        </div>
        <div className="contrast__arrow" aria-hidden="true">
          <svg viewBox="0 0 48 16" width="48" height="16"><path d="M2 8h40" className="loop-wire loop-wire--test" /><path d="M40 3l6 5-6 5z" fill="var(--edge-strong)" /></svg>
        </div>
        <div className="contrast contrast--test">
          <h3>Demonstrating an improvement</h3>
          <p>Run the original and the revised graph on later cases that were not used to choose the revision, scored by a rule declared in advance.</p>
          <p className="contrast__state">Requires a separate comparison</p>
        </div>
      </div>
    </div>
  );
}

type InvestigationScore = { correct: number; total: number };
type InvestigationCampaign = {
  id: string; model: string; complete: boolean; reported_cost_usd: string;
  learners?: Array<{ first_proposal_heldout: InvestigationScore; heldout: InvestigationScore; transfer: InvestigationScore }>;
};

function InvestigationResults({ result }: { result: Evidence }) {
  const campaigns = result.data.campaigns as InvestigationCampaign[];
  const score = (s: InvestigationScore) => `${s.correct}/${s.total}`;
  return <div className="diagnosis">
    {campaigns.filter(c => c.learners?.length).map(c => <section key={c.id}>
      <h3 className="block-head">{c.id}{c.complete ? '' : ' — controls incomplete'}</h3>
      <p>{c.model} · ${Number(c.reported_cost_usd).toFixed(4)} reported inference cost</p>
      <table className="diagnosis__table">
        <thead><tr><th>Learner</th><th>First proposal</th><th>Frozen final</th><th>Renamed schema</th></tr></thead>
        <tbody>{c.learners?.map((l, i) => <tr key={i}>
          <th>{i + 1}{i === 0 ? ' (primary)' : ''}</th><td>{score(l.first_proposal_heldout)}</td><td>{score(l.heldout)}</td><td>{score(l.transfer)}</td>
        </tr>)}</tbody>
      </table>
    </section>)}
    <p>{campaigns.filter(c => !c.complete).length} incomplete attempts remain in the saved record and total cost. Ratios use the declared numerical tolerance; findings and unresolved sets must match exactly.</p>
    <p>Repeated learners share the same model and inputs. Improvements across versions do not isolate changes to model, prompts or execution.</p>
    <a href={result.source.url} target="_blank" rel="noreferrer">Read the saved inputs, outputs and costs</a>
  </div>;
}

type ObservationScore = { correct: number; total: number; unsupported: number; errors: number };
type AdvanceStudy = {
  id: string; complete: boolean; calls: number; reported_cost_usd: string;
  model: string; reasoning_effort: string;
};
type AdvanceReceipt = Record<string, unknown> & {
  schema: 'zenith_advance_campaign_v1'; summary: string; status: string;
  total_calls: number; total_reported_cost_usd: string;
  conformance_studies: AdvanceStudy[]; memory: Record<string, unknown>;
};

function validAdvanceReceipt(data: Record<string, unknown>): data is AdvanceReceipt {
  const cost = (value: unknown) => typeof value === 'string' && value.trim() !== ''
    && Number.isFinite(Number(value)) && Number(value) >= 0;
  const count = (value: unknown) => typeof value === 'number' && Number.isInteger(value) && value >= 0;
  return data.schema === 'zenith_advance_campaign_v1' && typeof data.summary === 'string'
    && typeof data.status === 'string' && count(data.total_calls) && cost(data.total_reported_cost_usd)
    && data.memory !== null && typeof data.memory === 'object' && !Array.isArray(data.memory)
    && Array.isArray(data.conformance_studies) && data.conformance_studies.every(value => {
      if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
      const row = value as Record<string, unknown>;
      return typeof row.id === 'string' && typeof row.complete === 'boolean'
        && count(row.calls) && cost(row.reported_cost_usd)
        && typeof row.model === 'string' && typeof row.reasoning_effort === 'string';
    });
}

function AdvanceResults({ result, site }: { result: Evidence; site: Site }) {
  const data = result.data as AdvanceReceipt;
  return <div className="diagnosis">
    <h3 className="block-head">{data.status === 'complete' ? 'Advance campaign analysis complete' : 'Advance campaign analysis pending'}</h3>
    <p>Advance is the name of an earlier group of experiments. Some compared repaired programs with reference software; others tested what a separate learner remembered after a sequence of actions. Their results are reported separately below.</p>
    <p>{data.summary}</p>
    <p>{data.total_calls} recorded call attempts; ${Number(data.total_reported_cost_usd).toFixed(4)} reported inference cost across the recorded Advance campaign.</p>
    {typeof data.accounting_boundary === 'string' && <p>{data.accounting_boundary}</p>}
    <p>Analysis completion includes stopped studies and unresolved results. Each study retains its own construction and evaluation status.</p>
    <table className="diagnosis__table">
      <caption>Earlier experiments comparing programs with reference software</caption>
      <thead><tr><th>Study, model and reasoning setting</th><th>Program-writing stage</th><th>Requests to the AI and reported cost</th></tr></thead>
      <tbody>{data.conformance_studies.map(study => <tr key={study.id}>
        <th scope="row">{study.id}<br />{study.model}; {study.reasoning_effort}</th>
        <td>{study.complete ? 'Complete' : 'Incomplete'}</td>
        <td>{study.calls} attempts<br />${Number(study.reported_cost_usd).toFixed(4)}</td>
      </tr>)}</tbody>
    </table>
    {typeof data.memory.summary === 'string' && <p>{data.memory.summary}</p>}
    <p>The memory experiment asks whether the learner can predict later behavior after earlier actions. Its programs, test inputs, costs and limits are described separately in the linked research notes.</p>
    <a href={result.source.url} target="_blank" rel="noreferrer">Read the saved Advance experiment results and costs</a>
    <HistoricalReceipts site={site} />
  </div>;
}

type ProgressScore = { correct: number; total: number; errors: number };
type ProgressLearner = {
  native_configurations: number; authored_native_families: number;
  conditions: { ordinary_witness: { acquisition_source_calls: number };
    generic_singletons: { acquisition_source_calls: number } };
  ordinary_minus_generic_acquisition_source_calls: number; boundary: string;
};
type ProgressStudy = {
  id: string; version: string; stage: 'qualification' | 'diagnostic'; complete: boolean;
  model: string; reasoning_effort: string; parent_episodes: number;
  actual_calls: number; reported_cost_usd: string; unknown_cost_calls: number;
  qualification?: { passed: boolean };
  forfeited?: boolean; forfeiture_reason?: string;
  panel_summary?: { confirmation?: { overall?: Record<string, ProgressScore> } };
};
type ProgressReceipt = Record<string, unknown> & {
  schema: 'zenith_progress_campaign_report_v1'; summary: string; status: string;
  claim_boundary: string; conformance_studies: ProgressStudy[]; learner: ProgressLearner | null;
};

function progressStatusLabel(status: string): string {
  return ({ complete: 'comparison complete', diagnostic_pending: 'comparison in progress',
    qualification_failed: 'preliminary interface test failed', protocol_deviation: 'the experiment departed from its written procedure',
    pending: 'results pending' } as Record<string, string>)[status] ?? 'status unavailable';
}

function validProgressReceipt(data: Record<string, unknown>): data is ProgressReceipt {
  const cost = (value: unknown) => typeof value === 'string' && value.trim() !== ''
    && Number.isFinite(Number(value)) && Number(value) >= 0;
  const count = (value: unknown) => typeof value === 'number' && Number.isInteger(value) && value >= 0;
  const record = (value: unknown): value is Record<string, unknown> => value !== null
    && typeof value === 'object' && !Array.isArray(value);
  const learner = (value: unknown) => value === null || (record(value)
    && count(value.native_configurations) && count(value.authored_native_families)
    && typeof value.ordinary_minus_generic_acquisition_source_calls === 'number'
    && Number.isInteger(value.ordinary_minus_generic_acquisition_source_calls)
    && typeof value.boundary === 'string' && record(value.conditions)
    && record(value.conditions.ordinary_witness) && count(value.conditions.ordinary_witness.acquisition_source_calls)
    && record(value.conditions.generic_singletons) && count(value.conditions.generic_singletons.acquisition_source_calls));
  const scores = (value: unknown) => record(value) && Object.values(value).every(score =>
    record(score) && count(score.correct) && count(score.total) && count(score.errors)
      && Number(score.correct) <= Number(score.total));
  return data.schema === 'zenith_progress_campaign_report_v1' && typeof data.summary === 'string'
    && typeof data.status === 'string' && typeof data.claim_boundary === 'string'
    && record(data.source_bindings) && learner(data.learner)
    && Array.isArray(data.conformance_studies) && data.conformance_studies.every(value => {
      if (!record(value)) return false;
      const row = value as Record<string, unknown>;
      return typeof row.id === 'string' && typeof row.version === 'string'
        && typeof row.complete === 'boolean'
        && (row.stage === 'qualification' || row.stage === 'diagnostic')
        && count(row.parent_episodes) && count(row.actual_calls) && count(row.unknown_cost_calls)
        && cost(row.reported_cost_usd)
        && typeof row.model === 'string' && typeof row.reasoning_effort === 'string'
        && (row.forfeited === undefined || typeof row.forfeited === 'boolean')
        && (row.forfeiture_reason === undefined || typeof row.forfeiture_reason === 'string')
        && (row.stage !== 'diagnostic' || (record(row.panel_summary)
          && record(row.panel_summary.confirmation)
          && scores(row.panel_summary.confirmation.overall)));
    });
}

function ProgressResults({ result, site }: { result: Evidence; site: Site }) {
  const data = result.data as ProgressReceipt;
  const diagnostic = data.conformance_studies.find(study => study.stage === 'diagnostic');
  const confirmation = diagnostic?.panel_summary?.confirmation?.overall;
  const roles = ['parent', 'repair_only', 'fixed', 'ordinary', 'direct_batch', 'direct_masked', 'direct_adaptive'];
  const heading = data.status === 'complete' ? 'Repairing database, cache and text programs'
    : data.status === 'qualification_failed' ? 'The preliminary interface test did not pass'
      : data.status === 'protocol_deviation' ? 'The experiment departed from its written procedure'
        : 'Repair experiment results pending';
  return <div className="diagnosis">
    <h3 className="block-head">{heading}</h3>
    <p>Zenith asks the model to repair programs that imitate SQLite database operations, a cache that stores recently used items, or UTF-8 text decoding. It compares each answer with the actual software. A correct answer agrees on that test input; the totals below are not a proof that every input will work.</p>
    {diagnostic && <p>{diagnostic.actual_calls} model calls; ${diagnostic.reported_cost_usd} reported inference cost.</p>}
    {confirmation?.repair_only && confirmation.parent && <p>
      Repair alone: {confirmation.parent.correct}/{confirmation.parent.total} → {confirmation.repair_only.correct}/{confirmation.repair_only.total} correct answers.
      {roles.slice(2).some(role => confirmation[role]) && roles.slice(2).filter(role => confirmation[role]).every(role =>
        confirmation[role].total === confirmation.repair_only.total && confirmation[role].correct <= confirmation.repair_only.correct)
        && ' Extra investigation does not beat it in this comparison.'}
    </p>}
    {diagnostic && confirmation && <table className="diagnosis__table">
      <caption>Answers on additional inputs, tried after the repairs were chosen</caption>
      <thead><tr><th>Condition</th><th>Correct / total</th></tr></thead>
      <tbody>{roles.filter(role => confirmation[role]).map(role => <tr key={role}>
        <th scope="row">{{ parent: 'Starting program', repair_only: 'Repair only', fixed: 'Tests chosen in advance + repair', ordinary: 'Saved tester + repair', direct_batch: 'Tests chosen together + repair', direct_masked: 'Test answers hidden + repair', direct_adaptive: 'See each answer before the next test + repair' }[role] ?? role}</th>
        <td>{confirmation[role].correct}/{confirmation[role].total}</td>
      </tr>)}</tbody>
    </table>}
    <p>Tests chosen in advance, tests chosen by the model, and a repair request with no new tests are compared on the same starting programs. The examples were written for this study; repeated versions of them are not independent real-world applications.</p>
    <p><a href={result.source.url} target="_blank" rel="noreferrer">Read the saved repair results and costs</a></p>
    <details className="source-doc">
      <summary>How the model interface was tested, costs and full results</summary>
      <p>Before comparing repair methods, a separate preliminary test checks whether the model can send requests in the required format and use the allowed operations. Passing that preliminary test does not establish that its repairs work. The records below keep these stages separate.</p>
      <details><summary>Original technical summary from the saved result file</summary>
      <p>These two paragraphs quote the experiment record. In this record, a “parent” is a starting program, “confirmation” means tests tried after choosing the repair, and “acquisition source calls” are executions of the reference software. The ordinary-language explanation and scores appear above.</p>
      <p>{data.summary}</p>
      <p>{data.claim_boundary}</p>
      </details>
    {data.conformance_studies.length > 0 && <table className="diagnosis__table">
      <caption>Preliminary interface tests and repair comparisons, reported separately</caption>
      <thead><tr><th>Study, model and reasoning setting</th><th>Starting program examples</th><th>Requests to the AI and reported cost</th></tr></thead>
      <tbody>{data.conformance_studies.map(study => <tr key={study.id}>
        <th scope="row">{study.version} {study.stage === 'qualification' ? 'preliminary interface test' : 'repair comparison'}: {study.id}<br />{study.model}; {study.reasoning_effort}</th>
        <td>{study.parent_episodes}{study.forfeited ? <><br />Repair comparison not completed</>
          : study.stage === 'qualification' && study.qualification && <><br />{study.qualification.passed ? 'Interface passed' : 'Interface did not pass'}</>}</td>
        <td>{study.actual_calls} attempts<br />${Number(study.reported_cost_usd).toFixed(4)} reported{study.unknown_cost_calls > 0 && <><br />{study.unknown_cost_calls} unknown-charge attempts</>}</td>
      </tr>)}</tbody>
    </table>}
    {data.conformance_studies.filter(study => study.forfeited && study.forfeiture_reason).map(study =>
      <p key={`${study.id}-forfeiture`}>{study.version} repair comparison not completed: {study.forfeiture_reason}</p>)}
    </details>
    {data.learner && <section id="evolve" aria-label="Separate learner memory experiment">
      <h3 className="block-head">Repairing the learner’s memory</h3>
      <p>This is a separate learning algorithm, not the AI-written tester above. It tries to predict how software will respond after a sequence of actions. We repaired it to retain the earlier actions that exposed an incorrect prediction, along with the later question that revealed the error.</p>
      <p>The repaired learner ran the reference software {data.learner.conditions.ordinary_witness.acquisition_source_calls.toLocaleString('en-US')} times to collect answers. A comparison using generic one-action questions needed {data.learner.conditions.generic_singletons.acquisition_source_calls.toLocaleString('en-US')}. These are software executions, not requests to an AI. When we tried additional inputs later, the learner still made prediction errors.</p>
      <details className="source-doc"><summary>Separate learner comparison</summary>
      <p>{data.learner.native_configurations} settings of the reference software, covering {data.learner.authored_native_families} groups of examples written for this study.</p>
      <p>Limits recorded in the original research file: <q>{data.learner.boundary}</q></p>
      <table className="diagnosis__table">
        <caption>Number of executions used to learn from the reference software</caption>
        <thead><tr><th>How the learner chooses questions</th><th>Software executions</th></tr></thead>
        <tbody><tr><th scope="row">Retain the actions that exposed an error</th><td>{data.learner.conditions.ordinary_witness.acquisition_source_calls}</td></tr>
          <tr><th scope="row">Use generic one-action questions</th><td>{data.learner.conditions.generic_singletons.acquisition_source_calls}</td></tr></tbody>
      </table>
      </details>
      {site.documents['continuation-learner'] && <SourceDocument url={site.documents['continuation-learner']} />}
    </section>}
    <HistoricalReceipts site={site} />
  </div>;
}

function HistoricalReceipts({ site }: { site: Site }) {
  return <details className="source-doc">
    <summary>Earlier experiment records</summary>
    <ul>{['advance-campaign', 'observation-learning-result', 'decomposition-result', 'investigation-learning-result']
      .filter(id => id !== site.active_evidence_id).map(id =>
      site.evidence[id] ? <li key={id}><a href={apiUrl(site.evidence[id])} target="_blank" rel="noreferrer">Historical: {RECEIPT_LABEL[id]}</a></li> : null)}</ul>
  </details>;
}

const CLIENT_ARMS = [
  ['procedure', 'Saved learned tester'], ['ordinary_reuse', 'Saved ordinary tester'],
  ['same_history', 'New AI, earlier results'], ['cold', 'New AI, no earlier results'], ['fixed', 'Fixed tests'],
] as const;
const CLIENT_VERSIONS = [
  { id: 'client-investigation', label: 'v1, reasoning none', protocol: 'client-investigation-protocol' },
  { id: 'client-investigation-v2', label: 'v2, reasoning none', protocol: 'client-investigation-protocol-v2' },
  { id: 'client-investigation-v2-low', label: 'v2, reasoning low', protocol: 'client-investigation-protocol-v2' },
] as const;
type ClientArm = typeof CLIENT_ARMS[number][0];
type ClientMetric = {
  failed_targets_detected: number; total_failing_targets: number;
  query_slots: number; valid_probes: number; model_call_attempts: number;
  runs: number; not_run_targets: number;
};
type ClientReceipt = Record<string, unknown> & {
  schema: 'zenith_client_investigation_report_v1'; complete: boolean;
  protected_panel_opened: boolean; target_count: number; total_failing_targets: number;
  model_attempts: number; reported_model_cost_usd: string; unknown_cost_attempts: number;
  model: string; reasoning_effort: string; boundary: string;
  arm_metrics: Record<ClientArm, ClientMetric>;
  artifacts: Record<'procedure' | 'ordinary_reuse', { error: string | null }>;
};

function validClientReceipt(data: Record<string, unknown>): data is ClientReceipt {
  const count = (value: unknown) => typeof value === 'number' && Number.isInteger(value) && value >= 0;
  const record = (value: unknown): value is Record<string, unknown> => value !== null
    && typeof value === 'object' && !Array.isArray(value);
  return data.schema === 'zenith_client_investigation_report_v1'
    && typeof data.complete === 'boolean' && typeof data.protected_panel_opened === 'boolean'
    && count(data.target_count) && count(data.total_failing_targets)
    && Number(data.total_failing_targets) <= Number(data.target_count)
    && count(data.model_attempts) && count(data.unknown_cost_attempts)
    && typeof data.reported_model_cost_usd === 'string' && data.reported_model_cost_usd.trim() !== ''
    && Number.isFinite(Number(data.reported_model_cost_usd)) && Number(data.reported_model_cost_usd) >= 0
    && typeof data.model === 'string' && typeof data.reasoning_effort === 'string'
    && typeof data.boundary === 'string' && record(data.arm_metrics) && record(data.artifacts)
    && ['procedure', 'ordinary_reuse'].every(arm => {
      const artifact = (data.artifacts as Record<string, unknown>)[arm];
      return record(artifact) && (artifact.error === null || typeof artifact.error === 'string');
    })
    && CLIENT_ARMS.every(([arm]) => {
      const metric = (data.arm_metrics as Record<string, unknown>)[arm];
      return record(metric) && count(metric.failed_targets_detected)
        && metric.total_failing_targets === data.total_failing_targets
        && Number(metric.failed_targets_detected) <= Number(metric.total_failing_targets)
        && count(metric.query_slots) && count(metric.valid_probes)
        && Number(metric.valid_probes) <= Number(metric.query_slots)
        && count(metric.model_call_attempts) && count(metric.runs) && count(metric.not_run_targets)
        && Number(metric.runs) + Number(metric.not_run_targets) <= Number(data.target_count);
    });
}

function ClientStudy({ site }: { site: Site }) {
  const versions = CLIENT_VERSIONS.filter(version => site.evidence[version.id]);
  const latest = versions.at(-1);
  const urls = versions.map(version => site.evidence[version.id]);
  const receipts = useAsync(() => Promise.all(versions.map(async version => {
    try {
      return { version, result: await api.evidence(site.evidence[version.id]), error: null };
    } catch (error) {
      return { version, result: null, error: error instanceof Error ? error.message : String(error) };
    }
  })), [urls.join('|')]);
  const selected = receipts.status === 'ready' ? receipts.value.find(row => row.version.id === latest?.id) : null;
  const method = latest ? site.documents[latest.protocol] : site.documents['client-investigation-protocol'];
  const explanation = latest ? site.documents[latest.id] : undefined;
  return <section className="diagnosis" aria-labelledby="client-study-title">
    <h3 id="client-study-title" className="block-head">Reusable tests</h3>
    <p>The model first sees tests and results from programs that import data into a database. It then writes a tester for different programs that transfer money between accounts in the same kind of database. A tester finds a fault when an allowed test exposes a disagreement with the expected behavior.</p>
    {latest && <p>Latest published version: {latest.label}. “Reasoning” is the provider’s setting for the model’s internal reasoning effort.</p>}
    {!latest ? <p role="status">Client pilot results pending. No result file has been published for the tester-reuse experiment.</p>
      : receipts.status === 'loading' ? <Loading what="the tester-reuse result file" />
        : receipts.status === 'error' || selected?.error
          ? <p role="status">The tester-reuse result file could not be loaded: {selected?.error ?? (receipts.status === 'error' ? receipts.message : '')}</p>
          : selected?.result && validClientReceipt(selected.result.data)
            ? <ClientResults result={selected.result} version={selected.version.id} />
            : <p role="status">The tester-reuse result file uses an unsupported format; no outcomes are displayed.</p>}
    {receipts.status === 'ready' && receipts.value.length > 0 && <>
      <details className="source-doc"><summary>Earlier client attempts</summary>
      <p>Each version keeps its own prompts, source, results and costs.</p>
      <ul>{receipts.value.map(row => <li key={row.version.id}>
        <strong>{row.version.label}:</strong>{' '}
        {row.result && validClientReceipt(row.result.data)
          ? <ClientVersionSummary data={row.result.data} />
          : row.error ? 'Result file could not be loaded.' : 'The result file uses an unsupported format; no outcome is shown.'}{' '}
        <a href={apiUrl(site.evidence[row.version.id])} target="_blank" rel="noreferrer">Result data</a>
        {site.documents[row.version.id] && <>{' · '}<a href={apiUrl(site.documents[row.version.id])} target="_blank" rel="noreferrer">Analysis</a></>}
      </li>)}</ul>
      </details>
    </>}
    {method && <p><a href={apiUrl(method)} target="_blank" rel="noreferrer">Read the client-pilot protocol</a></p>}
    {explanation && <SourceDocument url={explanation} />}
  </section>;
}

function ClientVersionSummary({ data }: { data: ClientReceipt }) {
  const procedure = data.arm_metrics.procedure;
  const ordinary = data.arm_metrics.ordinary_reuse;
  if (data.artifacts.procedure.error) return <>The generated tester could not run; {procedure.not_run_targets} later programs not tested. {ordinary.runs > 0 && ordinary.query_slots === 0 ? 'The ordinary tester ran but tried no inputs on the later programs.' : ''}</>;
  if (data.complete && procedure.runs > 0 && ordinary.runs > 0 && procedure.query_slots === 0 && ordinary.query_slots === 0)
    return <>Both saved testers stopped without trying any inputs on the later programs.</>;
  return <>{data.complete && data.protected_panel_opened
    ? `Saved learned tester ${procedure.failed_targets_detected}/${procedure.total_failing_targets}; ordinary reuse ${ordinary.failed_targets_detected}/${ordinary.total_failing_targets}.`
    : 'Results on the later test inputs are not yet available.'}</>;
}

function ClientResults({ result, version }: { result: Evidence; version: string }) {
  const data = result.data as ClientReceipt;
  return <>
    <p>{data.complete ? 'Pilot complete.' : 'Pilot incomplete.'} {data.model_attempts} recorded model attempts; ${data.reported_model_cost_usd} reported inference cost. {data.model}; reasoning {data.reasoning_effort}.</p>
    {data.unknown_cost_attempts > 0 && <p>{data.unknown_cost_attempts} attempts have unresolved charges.</p>}
    {data.complete && data.protected_panel_opened ? <>
      <p>{data.target_count} later database programs were tested; {data.total_failing_targets} contained a known fault.</p>
      <table className="diagnosis__table">
        <caption>Faults detected and work on later programs</caption>
        <thead><tr><th>Method</th><th>Faults found</th><th>Allowed tests / attempted tests</th><th>Requests to the AI</th></tr></thead>
        <tbody>{CLIENT_ARMS.map(([arm, label]) => <tr key={arm}>
          <th scope="row">{label}</th>
          <td>{data.arm_metrics[arm].not_run_targets > 0 ? <>Not run<br />{data.arm_metrics[arm].not_run_targets} programs</>
            : <>{data.arm_metrics[arm].failed_targets_detected}/{data.arm_metrics[arm].total_failing_targets}</>}</td>
          <td>{data.arm_metrics[arm].valid_probes}/{data.arm_metrics[arm].query_slots}</td>
          <td>{data.arm_metrics[arm].model_call_attempts}</td>
        </tr>)}</tbody>
      </table>
      {(['procedure', 'ordinary_reuse'] as const).filter(arm => data.artifacts[arm].error).map(arm =>
        <p key={arm}>{arm === 'procedure' ? 'Saved learned tester' : 'Saved ordinary tester'} program error: {data.artifacts[arm].error}</p>)}
      {data.arm_metrics.procedure.runs > 0 && data.arm_metrics.ordinary_reuse.runs > 0
        && data.arm_metrics.procedure.query_slots === 0 && data.arm_metrics.ordinary_reuse.query_slots === 0
        && <p>Neither saved tester tried an input on the later programs. This pilot does not establish an advantage from reuse.</p>}
      {data.arm_metrics.procedure.query_slots > 0 && data.arm_metrics.ordinary_reuse.query_slots > 0
        && data.arm_metrics.procedure.failed_targets_detected === data.arm_metrics.ordinary_reuse.failed_targets_detected
        && <p>The saved learned tester matched the ordinary reusable tester on detected faults. This comparison does not establish an advantage from learned reuse.</p>}
      {version === 'client-investigation-v2-low' && <p>In this published version, both generated testers repeat the same test input and ignore the response when deciding what to try next.</p>}
      {data.arm_metrics.procedure.model_call_attempts === 0 && data.arm_metrics.ordinary_reuse.model_call_attempts === 0
        && <p>The total cost includes the model requests used to learn from the earlier examples and write the testers. The table counts only work on the later programs. Attempted tests include invalid and repeated requests; an allowed test need not find a fault. A request to the AI is a separate operation from running a software test.</p>}
      <p>These examples were written for this study. They do not establish performance on independent software or how often the tester would report a fault incorrectly.</p>
    </> : <p>Results on the later programs appear only after the tester has been saved unchanged and those programs have been tested.</p>}
    <details className="source-doc"><summary>Scope of this result</summary><p>{data.boundary}</p></details>
    <p><a href={result.source.url} target="_blank" rel="noreferrer">Read the saved tester-reuse results and costs</a></p>
  </>;
}

type ObservationComparison = {
  worlds: number; mean_accuracy_difference: number; paired_bootstrap_95_percentile: [number, number];
  wins: number; ties: number; losses: number;
};
type ObservationReceipt = {
  status: string; complete: boolean; campaign: string; planned_worlds: number; frozen_worlds: number;
  model: string; provider_slug: string; total_calls: number; total_reported_cost_usd: string;
  unreported_cost_calls: number; unreported_cost_reservations_usd: string; cost_bounds_usd: [string, string];
  aggregate: Record<string, ObservationScore> | null;
  comparisons: Record<string, ObservationComparison> | null;
  failure: { error?: string } | null; boundary: string;
};

function observationComplete(data: ObservationReceipt): boolean {
  return data.complete === true && data.status === 'complete' && data.aggregate != null;
}

function observationStatus(data: ObservationReceipt): string {
  if (observationComplete(data)) return 'Protected evaluation complete';
  if (data.status === 'failed') return 'Campaign stopped';
  if (data.status === 'interrupted') return 'Campaign interrupted';
  if (data.status === 'pilot') return 'Pilot snapshot';
  if (data.status === 'running') return 'Campaign running';
  return 'Partial snapshot';
}

const OBSERVATION_ARMS = [
  ['incremental', 'Incremental (primary)'], ['archive', 'Full construction archive'],
  ['fresh', 'Fresh from final evidence'], ['freeze_and_grow', 'Frozen first checkpoint (control)'],
  ['empty_history', 'Final program, empty history (control)'], ['cold', 'Unlearned program (control)'],
] as const;

function ObservationResults({ result }: { result: Evidence }) {
  const data = result.data as unknown as ObservationReceipt;
  const complete = observationComplete(data);
  const points = (value: number) => `${(value * 100).toFixed(1)} percentage points`;
  return <div className="diagnosis">
    <h3 className="block-head">{observationStatus(data)}</h3>
    <p>This earlier experiment asks the model to write programs that predict a software library’s responses. The programs are saved unchanged before Zenith tries the later test inputs. These later inputs are called the protected evaluation because their answers were not supplied while the model was writing the programs.</p>
    <p>Campaign: {data.campaign}</p>
    <p>{data.frozen_worlds}/{data.planned_worlds} planned sets of reference-software examples have been saved unchanged. Model: {data.model}; provider: {data.provider_slug}.</p>
    <p>{data.total_calls} requests to the AI, including preliminary requests to test the connection; ${Number(data.total_reported_cost_usd).toFixed(4)} reported cost.</p>
    {data.unreported_cost_calls > 0 && <p>Billing remains unresolved for {data.unreported_cost_calls} {data.unreported_cost_calls === 1 ? 'call' : 'calls'}; ${Number(data.unreported_cost_reservations_usd).toFixed(4)} remains reserved. Cost bounds: ${Number(data.cost_bounds_usd[0]).toFixed(4)} to ${Number(data.cost_bounds_usd[1]).toFixed(4)}.</p>}
    {data.failure?.error && <p role="status">Recorded failure: {data.failure.error}</p>}
    {complete ? <>
      <table className="diagnosis__table">
        <caption>Correct answers and errors on the later test inputs</caption>
        <thead><tr><th>Program-writing method</th><th>Answers matching the reference</th><th>Exact claims without supporting evidence</th><th>Execution or response errors</th></tr></thead>
        <tbody>{OBSERVATION_ARMS.map(([id, label]) => {
          const score = data.aggregate?.[id];
          return score ? <tr key={id}><th>{label}</th><td>{score.correct}/{score.total}</td><td>{score.unsupported}</td><td>{score.errors}</td></tr> : null;
        })}</tbody>
      </table>
      {data.comparisons && <table className="diagnosis__table">
        <caption>Difference in correct-answer rates on the same reference-software examples</caption>
        <thead><tr><th>Comparison</th><th>Mean difference</th><th>Descriptive 95% interval</th><th>Wins / ties / losses</th></tr></thead>
        <tbody>{OBSERVATION_ARMS.filter(([id]) => id === 'archive' || id === 'fresh' || id === 'freeze_and_grow').map(([id, label]) => {
          const comparison = data.comparisons?.[id];
          return comparison ? <tr key={id}><th>{label}</th><td>{points(comparison.mean_accuracy_difference)}</td><td>{points(comparison.paired_bootstrap_95_percentile[0])} to {points(comparison.paired_bootstrap_95_percentile[1])}</td><td>{comparison.wins} / {comparison.ties} / {comparison.losses}</td></tr> : null;
        })}</tbody>
      </table>}
      <p>The examples use different settings of one software family. These comparisons do not establish success on unrelated software or general intelligence.</p>
    </> : <p>Later test results appear only after the programs have been written, saved unchanged and tested. Counts of saved examples or AI requests do not establish that the model learned a useful program.</p>}
    <p>{data.boundary}</p>
    <a href={result.source.url} target="_blank" rel="noreferrer">Read the saved observation-study results and costs</a>
  </div>;
}

function ResultsFigure({ chapter, labGraph, site }: { chapter: Chapter; labGraph: Graph | null; site: Site }) {
  const windowUrl = chapter.evidence_urls.find((u) => u.endsWith('window-result')) ?? site.evidence['window-result'];
  const condUrl = chapter.evidence_urls.find((u) => u.endsWith('conditional-result')) ?? site.evidence['conditional-result'];
  // The chapter binds whichever receipt the current edition has; the view
  // follows the receipt's schema.
  const bound = activeEvidenceUrl(site, chapter);
  const progressActive = site.active_evidence_id === 'progress-campaign';
  const advanceActive = site.active_evidence_id === 'advance-campaign';
  const kind = useAsync<Evidence | null>(() => (bound ? api.evidence(bound) : Promise.resolve(null)), [bound]);
  const isPreparation = kind.status === 'ready' && String(kind.value?.data.schema ?? '').startsWith('zenith_demo_preparation');
  const sourcesUrl = site.evidence.sources;
  const sources = useAsync<Evidence | null>(
    () => (isPreparation && sourcesUrl ? api.evidence(sourcesUrl) : Promise.resolve(null)),
    [isPreparation, sourcesUrl],
  );
  const evidence = useAsync<[Evidence, Evidence] | null>(
    () =>
      kind.status === 'ready' && !isPreparation && !progressActive && !advanceActive && windowUrl && condUrl
        ? Promise.all([api.evidence(windowUrl), api.evidence(condUrl)])
        : Promise.resolve(null),
    [kind.status, isPreparation, progressActive, advanceActive, windowUrl, condUrl],
  );
  if (progressActive) {
    if (!bound) return <><p role="status">Current campaign results pending. No current result file is published; earlier experiment results are listed separately.</p><HistoricalReceipts site={site} /></>;
    if (kind.status === 'error') return <><p role="status">The current experiment result file could not be loaded: {kind.message}</p><HistoricalReceipts site={site} /></>;
    if (kind.status === 'ready') return kind.value && validProgressReceipt(kind.value.data)
      ? <ProgressResults result={kind.value} site={site} />
      : <><p role="status">The current experiment result file uses an unsupported format; no outcomes are displayed.</p><HistoricalReceipts site={site} /></>;
    return <Loading what="the current experiment result file" />;
  }
  if (advanceActive) {
    if (!bound) return <><p role="status">Advance campaign results pending. No result file is published for this experiment; earlier results are listed separately.</p><HistoricalReceipts site={site} /></>;
    if (kind.status === 'error') return <><p role="status">The Advance experiment result file could not be loaded: {kind.message}</p><HistoricalReceipts site={site} /></>;
    if (kind.status === 'ready') return kind.value && validAdvanceReceipt(kind.value.data)
      ? <AdvanceResults result={kind.value} site={site} />
      : <><p role="status">The Advance experiment result file uses an unsupported format; no outcomes are displayed.</p><HistoricalReceipts site={site} /></>;
    return <Loading what="the Advance experiment result file" />;
  }
  if (kind.status === 'ready' && kind.value?.data.schema === 'zenith_learning_evidence_v1') {
    return <InvestigationResults result={kind.value} />;
  }
  if (kind.status === 'ready' && kind.value?.data.schema === 'zenith_observation_learning_evidence_v1') {
    return <><ObservationResults result={kind.value} />
      {site.evidence['observation-screens'] && <p><a href={site.evidence['observation-screens']} target="_blank" rel="noreferrer">Read the follow-on repair, candidate search and program-combination results</a></p>}
    </>;
  }
  if (site.active_evidence_id === 'observation-learning-result') {
    if (kind.status === 'error') return <p role="status">The observation experiment result file could not be loaded: {kind.message}</p>;
    if (!bound) return <p role="status">Results pending. The current study has no published observation result file. Scores on later inputs appear only after those tests have been run.</p>;
    if (kind.status === 'ready') return <p role="status">The observation experiment result file uses an unsupported format; no scores are displayed.</p>;
    return <Loading what="the observation experiment result file" />;
  }
  if (isPreparation && labGraph && kind.status === 'ready' && kind.value) {
    return (
      <>
        <p className="model-notice">
          <strong>Experimental research prototype.</strong> All observations in this demonstration are synthetic.
          Input preparation does not establish prediction accuracy.
        </p>
        <Preparation result={kind.value} sources={sources.status === 'ready' ? sources.value : null} labGraph={labGraph} localRuns={site.local_runs_enabled} />
      </>
    );
  }
  if (evidence.status === 'error') {
    return (
      <div className="model-notice">
        <p>
          <strong>The measured results are not available from this server</strong> ({evidence.message}). The
          paper’s Section 4 reports the execution study and its limits.
        </p>
        {chapter.paper_section && (
          <a href={apiUrl(chapter.paper_section.pdf_url)} target="_blank" rel="noreferrer">
            Read Section 4 in the paper (PDF)
          </a>
        )}
      </div>
    );
  }
  if (kind.status === 'error') {
    return <p className="inspector__warn">The result record could not be loaded: {kind.message}</p>;
  }
  if (evidence.status === 'loading' || kind.status === 'loading' || !labGraph || !evidence.value) return <Loading what="the recorded results" />;
  return (
    <>
      <p className="model-notice">
        <strong>Experimental research prototype.</strong> Saved execution records show what ran.
        They establish predictive accuracy only when paired with a defined evaluation.
      </p>
      <Results windowResult={evidence.value[0]} conditional={evidence.value[1]} labGraph={labGraph} localRuns={site.local_runs_enabled} />
    </>
  );
}

function NextFigure({ chapter }: { chapter: Chapter }) {
  const doc = useAsync<Doc | null>(() => (chapter.document_url ? api.document(chapter.document_url) : Promise.resolve(null)), [chapter.document_url]);
  return (
    <>
      <MechanismDiagram />
      {doc.status === 'ready' && doc.value && <SettingsIllustration doc={doc.value} />}
    </>
  );
}

function PaperSection({ site, paper }: { site: Site; paper: Paper | null }) {
  const currentPdf = paper?.pdf_current === true;
  const currentIds = site.active_evidence_id === 'progress-campaign'
    ? ['progress-campaign', [...CLIENT_VERSIONS].reverse().find(v => site.evidence[v.id])?.id]
    : Object.keys(site.evidence);
  return (
    <section className="paper-band" id="paper" aria-labelledby="paper-title">
      <div className="wrap paper-band__grid">
        <div>
          <h2 id="paper-title">Paper, code and instructions to repeat the experiments</h2>
          {currentPdf && <p><a className="button" href={apiUrl(paper.pdf_url)} target="_blank" rel="noreferrer">Read the paper (PDF)</a></p>}
          <p><a className="button" href={apiUrl(paper?.source.url ?? site.documents.paper ?? '/api/v1/documents/paper')}
            target="_blank" rel="noreferrer">Current LaTeX source on GitHub</a></p>
          <p>The current paper is stored as LaTeX, the text and formatting code used to prepare a research paper. The GitHub repository contains installation commands and examples you can run without an AI account. Its replay commands run the saved programs again and compare their behavior with the published results.</p>
          <p><a href="https://github.com/wcook04/plectis-zenith#try-it-without-an-account" target="_blank" rel="noreferrer">Run the examples or replay the evidence</a></p>
          {paper && <details>
            <summary>Compare the downloaded PDF with the saved file</summary>
            <p>SHA-256 is a checksum calculated from a file’s contents. Matching checksums show that the files contain the same bytes; they do not establish that the paper’s claims are correct.</p>
            <p>SHA-256 <code className="hash">{paper.pdf_sha256}</code></p>
            <CopyButton text={paper.pdf_sha256} label="Copy hash" />
          </details>}
          <h3 className="paper-aside__head">Current experiment records</h3>
          <ul className="plain-list">
            {Object.entries(site.evidence).filter(([id]) => currentIds.includes(id)).map(([id, url]) => (
              <li key={id}><a href={apiUrl(url)} target="_blank" rel="noreferrer">{RECEIPT_LABEL[id] ?? id.replace(/-/g, ' ')}</a></li>
            ))}
          </ul>
          <details className="source-doc">
            <summary>Earlier studies, graphs and paper edition</summary>
            <p>The financial studies and earlier graph experiments remain here as historical records.</p>
            {!currentPdf && <p>The PDF has no verified binding to the current source. <a href={apiUrl(paper?.pdf_url ?? '/assets/paper.pdf')} target="_blank" rel="noreferrer">Previous edition (PDF)</a></p>}
            <ul className="plain-list">
              {Object.entries(site.evidence).filter(([id]) => !currentIds.includes(id)).map(([id, url]) => (
                <li key={id}><a href={apiUrl(url)} target="_blank" rel="noreferrer">{RECEIPT_LABEL[id] ?? id.replace(/-/g, ' ')}</a></li>
              ))}
            </ul>
            <h3 className="paper-aside__head">Diagrams of the earlier program versions</h3>
            <p>Each box represents a source of data or a step in the program. An arrow means one step reads another step’s output. The diagram describes the intended dependencies; it does not show that the steps ran or that a prediction was correct. A profile is a version configured for a particular task, such as the earlier financial experiment.</p>
            <ul className="plain-list">
              {Object.entries(site.figures).map(([id, url]) => (
                <li key={id}><a href={apiUrl(url)} target="_blank" rel="noreferrer">{FIGURE_LABEL[id] ?? id.replace(/-/g, ' ')} (SVG)</a></li>
              ))}
            </ul>
          </details>
        </div>
        <div>
          <h3 className="paper-aside__head">References</h3>
          {paper ? (
            <ol className="refs refs--full">
              {paper.citations.map((citation) => (
                <li key={citation.id} id={`ref-${citation.id}`}>
                  {latexToText(citation.latex)}{' '}
                  <span className="refs__links">
                    ({citation.urls.map((url, i) => (
                      <span key={url}>
                        {i > 0 && ', '}
                        <a href={url} target="_blank" rel="noreferrer">
                          {linkLabel(url)}
                        </a>
                      </span>
                    ))})
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p role="status">Loading references…</p>
          )}
        </div>
      </div>
    </section>
  );
}
