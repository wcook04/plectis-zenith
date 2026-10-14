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
  'decomposition-result': 'Structural revision and synthetic rule-induction studies',
  'observation-learning-result': 'Native observation-learning study',
  'observation-screens': 'Follow-on repair, candidate search and composition tests',
  'investigation-learning-result': 'Historical operational investigation campaigns',
  sources: 'Where each input comes from, with file hashes',
  replacements: 'Synthetic multi-feed observations',
  'demo-result': 'Preparation record',
  observations: 'Synthetic observations',
  'window-result': 'Window experiment record',
  'conditional-result': 'Conditional continuation record',
};

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
        <p className="page-status" role="status">Loading the paper and graph…</p>
      </Shell>
    );
  }
  if (site.status === 'error') {
    return (
      <Shell>
        <div className="page-status" role="alert">
          <h1>The Zenith backend is not answering</h1>
          <p>
            This site reads everything from the read-only Zenith API ({site.message}). Start it from the repository
            root with <code>python -m zenith serve --port 4175</code> and reload.
          </p>
        </div>
      </Shell>
    );
  }
  return <Page site={site.value} paper={paper.status === 'ready' ? paper.value : null} />;
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
              <span className="notice-bar__extra"> Constructed experiments with measured native behavior.</span>
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
                  {chapter.evidence_kind === 'verified_preparation' ? 'Preparation' : (NAV_LABEL[chapter.id] ?? chapter.title)}
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
  const learningActive = Boolean(site.active_evidence_id === 'observation-learning-result'
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
          <a className="button" href={apiUrl(paper?.pdf_url ?? '/assets/paper.pdf')} target="_blank" rel="noreferrer">
            Read the paper (PDF)
          </a>
          <a className="button button--ghost" href="#lab">
            Explore the investigation
          </a>
          {byline && <span className="hero__byline">{byline}</span>}
        </div>
        </div>
        <nav className="hero__map" aria-labelledby="contents-caption">
          <table>
            <caption id="contents-caption">Contents and the status of the material in each section</caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="visually-hidden">Number</span>
                </th>
                <th scope="col">Section</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {site.chapters.map((chapter, i) => (
                <tr key={chapter.id} className={`map-row map-row--${chapter.evidence_kind}`}>
                  <td className="map-row__num">{i + 1}</td>
                  <th scope="row" className="map-row__title">
                    <a href={`#${chapter.id}`}>{chapter.title}</a>
                  </th>
                  <td className="map-row__kind">{EVIDENCE_KIND_LABEL[chapter.evidence_kind]?.label ?? chapter.evidence_kind}</td>
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
          paragraphs={
            chapter.id === 'lab' && !learningActive
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
            <ResultsFigure chapter={chapter} labGraph={lab.status === 'ready' ? lab.value : null} site={site} />
          )}
          {chapter.id === 'next' && !learningActive && <NextFigure chapter={chapter} />}
        </ChapterSection>
      ))}

      <PaperSection site={site} paper={paper} />
      <footer className="footer">
        <div className="wrap footer__inner">
          <p>
            <strong>Experimental research prototype.</strong> Constructed experiments measure native SQLite behavior.
            Their bounded results do not establish reliable production operation. Earlier synthetic examples remain historical.
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
  const url = chapter?.evidence_urls[0];
  const evidence = useAsync<Evidence | null>(() => (url ? api.evidence(url) : Promise.resolve(null)), [url]);
  const observationActive = site.active_evidence_id === 'observation-learning-result'
    || Boolean(site.evidence['observation-learning-result']);
  const sourcesUrl = observationActive || site.evidence['investigation-learning-result'] ? undefined : site.evidence.sources;
  const sources = useAsync<Evidence | null>(() => (sourcesUrl ? api.evidence(sourcesUrl) : Promise.resolve(null)), [sourcesUrl]);
  const composition = sources.status === 'ready' && sources.value ? compositionSentence(sources.value) : null;
  let summary: string | null = null;
  if (evidence.status === 'ready' && evidence.value) {
    const schema = String(evidence.value.data.schema ?? '');
    if (schema.startsWith('zenith_demo_preparation')) summary = preparationSummary(evidence.value);
    else if (schema.startsWith('zenith_original_feed_window')) summary = windowSummary(evidence.value);
    else if (schema === 'zenith_learning_evidence_v1') summary = `${evidence.value.data.total_calls} model calls; $${Number(evidence.value.data.total_reported_cost_usd).toFixed(4)} reported cost across all recorded attempts.`;
    else if (schema === 'zenith_observation_learning_evidence_v1') {
      const data = evidence.value.data as unknown as ObservationReceipt;
      summary = `Initial native comparison: ${observationStatus(data)}; ${data.total_calls} calls including canary attempts; $${Number(data.total_reported_cost_usd).toFixed(4)} reported cost.`;
    }
  }
  if (observationActive && !url) summary = 'Observation study results pending.';
  else if (observationActive && evidence.status === 'error') summary = 'Observation-study receipt unavailable.';
  else if (observationActive && evidence.status === 'ready' && evidence.value
    && evidence.value.data.schema !== 'zenith_observation_learning_evidence_v1') summary = 'Observation-study receipt schema unsupported.';
  if (!chapter) return null;
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
  children,
}: {
  chapter: Chapter;
  index: number;
  paper: Paper | null;
  latex: string | null;
  paragraphs?: string[];
  children: React.ReactNode;
}) {
  const copy = CHAPTER_COPY[chapter.id];
  return (
    <section className={`chapter chapter--${chapter.id}`} id={chapter.id} aria-labelledby={`${chapter.id}-title`}>
      <div className="wrap chapter__grid">
        <div className="chapter__text">
          <p className={`chapter__status status--${chapter.evidence_kind}`}>
            <span className="chapter__num">{String(index + 1).padStart(2, '0')}</span>
            <span>{EVIDENCE_KIND_LABEL[chapter.evidence_kind]?.label ?? chapter.evidence_kind}</span>
          </p>
          <h2 id={`${chapter.id}-title`}>{chapter.title}</h2>
          {EVIDENCE_KIND_LABEL[chapter.evidence_kind] && (
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
        <summary>Read the repository’s own explanation</summary>
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
    <p>{campaigns.filter(c => !c.complete).length} incomplete attempts remain in the receipt and total cost. Ratios use the declared numerical tolerance; findings and unresolved sets must match exactly.</p>
    <p>Repeated learners share the same model and inputs. Improvements across versions do not isolate changes to model, prompts or execution.</p>
    <a href={result.source.url} target="_blank" rel="noreferrer">Read the complete evidence receipt</a>
  </div>;
}

type ObservationScore = { correct: number; total: number; unsupported: number; errors: number };
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
    <p>Campaign: {data.campaign}</p>
    <p>{data.frozen_worlds}/{data.planned_worlds} source streams frozen. {data.model} via {data.provider_slug}.</p>
    <p>{data.total_calls} calls including canary attempts; ${Number(data.total_reported_cost_usd).toFixed(4)} reported inference cost.</p>
    {data.unreported_cost_calls > 0 && <p>Billing remains unresolved for {data.unreported_cost_calls} {data.unreported_cost_calls === 1 ? 'call' : 'calls'}; ${Number(data.unreported_cost_reservations_usd).toFixed(4)} remains reserved. Cost bounds: ${Number(data.cost_bounds_usd[0]).toFixed(4)} to ${Number(data.cost_bounds_usd[1]).toFixed(4)}.</p>}
    {data.failure?.error && <p role="status">Recorded failure: {data.failure.error}</p>}
    {complete ? <>
      <table className="diagnosis__table">
        <caption>Protected exact answers and conditional identification errors</caption>
        <thead><tr><th>Policy or control</th><th>Exact answers</th><th>Unsupported exact</th><th>Execution or response errors</th></tr></thead>
        <tbody>{OBSERVATION_ARMS.map(([id, label]) => {
          const score = data.aggregate?.[id];
          return score ? <tr key={id}><th>{label}</th><td>{score.correct}/{score.total}</td><td>{score.unsupported}</td><td>{score.errors}</td></tr> : null;
        })}</tbody>
      </table>
      {data.comparisons && <table className="diagnosis__table">
        <caption>Incremental accuracy minus each comparison, paired by native source</caption>
        <thead><tr><th>Comparison</th><th>Mean difference</th><th>Descriptive 95% interval</th><th>Wins / ties / losses</th></tr></thead>
        <tbody>{OBSERVATION_ARMS.filter(([id]) => id === 'archive' || id === 'fresh' || id === 'freeze_and_grow').map(([id, label]) => {
          const comparison = data.comparisons?.[id];
          return comparison ? <tr key={id}><th>{label}</th><td>{points(comparison.mean_accuracy_difference)}</td><td>{points(comparison.paired_bootstrap_95_percentile[0])} to {points(comparison.paired_bootstrap_95_percentile[1])}</td><td>{comparison.wins} / {comparison.ties} / {comparison.losses}</td></tr> : null;
        })}</tbody>
      </table>}
      <p>Configured sources are conditional replications in one native software family. These comparisons do not establish transfer across domains or general intelligence.</p>
    </> : <p>Protected outcome tables are unavailable until construction and the protected evaluation complete. Frozen stream counts and inference calls do not establish learning success.</p>}
    <p>{data.boundary}</p>
    <a href={result.source.url} target="_blank" rel="noreferrer">Read the complete observation-study receipt</a>
  </div>;
}

function ResultsFigure({ chapter, labGraph, site }: { chapter: Chapter; labGraph: Graph | null; site: Site }) {
  const windowUrl = chapter.evidence_urls.find((u) => u.endsWith('window-result')) ?? site.evidence['window-result'];
  const condUrl = chapter.evidence_urls.find((u) => u.endsWith('conditional-result')) ?? site.evidence['conditional-result'];
  // The chapter binds whichever receipt the current edition has; the view
  // follows the receipt's schema.
  const bound = chapter.evidence_urls[0];
  const kind = useAsync<Evidence | null>(() => (bound ? api.evidence(bound) : Promise.resolve(null)), [bound]);
  const isPreparation = kind.status === 'ready' && String(kind.value?.data.schema ?? '').startsWith('zenith_demo_preparation');
  const sourcesUrl = site.evidence.sources;
  const sources = useAsync<Evidence | null>(
    () => (isPreparation && sourcesUrl ? api.evidence(sourcesUrl) : Promise.resolve(null)),
    [isPreparation, sourcesUrl],
  );
  const evidence = useAsync<[Evidence, Evidence] | null>(
    () =>
      kind.status === 'ready' && !isPreparation && windowUrl && condUrl
        ? Promise.all([api.evidence(windowUrl), api.evidence(condUrl)])
        : Promise.resolve(null),
    [kind.status, isPreparation, windowUrl, condUrl],
  );
  if (kind.status === 'ready' && kind.value?.data.schema === 'zenith_learning_evidence_v1') {
    return <InvestigationResults result={kind.value} />;
  }
  if (kind.status === 'ready' && kind.value?.data.schema === 'zenith_observation_learning_evidence_v1') {
    return <><ObservationResults result={kind.value} />
      {site.evidence['observation-screens'] && <p><a href={site.evidence['observation-screens']} target="_blank" rel="noreferrer">Read the follow-on repair, candidate search and composition receipts</a></p>}
    </>;
  }
  if (site.active_evidence_id === 'observation-learning-result' || site.evidence['observation-learning-result']) {
    if (kind.status === 'error') return <p role="status">The observation-study receipt is unavailable: {kind.message}</p>;
    if (!bound) return <p role="status">Results pending. The current study has no published observation receipt. Protected scores will appear only after measured evaluation.</p>;
    if (kind.status === 'ready') return <p role="status">The observation-study receipt has an unsupported schema; no scores are displayed.</p>;
    return <Loading what="the observation-study receipt" />;
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
  return (
    <section className="paper-band" id="paper" aria-labelledby="paper-title">
      <div className="wrap paper-band__grid">
        <div>
          <h2 id="paper-title">The paper and its evidence</h2>
          <p>
            <a className="button" href={apiUrl(paper?.pdf_url ?? '/assets/paper.pdf')} target="_blank" rel="noreferrer">
              Read the paper (PDF)
            </a>
          </p>
          {paper && (
            <div className="paper-band__hash">
              <a href={paper.source.url} target="_blank" rel="noreferrer">
                LaTeX source on GitHub
              </a>
              <details>
                <summary>Verify the PDF</summary>
                <p>
                  SHA-256 <code className="hash">{paper.pdf_sha256}</code>
                </p>
                <CopyButton text={paper.pdf_sha256} label="Copy hash" />
              </details>
            </div>
          )}
          <h3 className="paper-aside__head">Records</h3>
          <ul className="plain-list">
            {Object.entries(site.evidence).map(([id, url]) => (
              <li key={id}>
                <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                  {RECEIPT_LABEL[id] ?? id.replace(/-/g, ' ')}
                </a>
              </li>
            ))}
          </ul>
          <h3 className="paper-aside__head">Historical graph profiles</h3>
          <ul className="plain-list">
            {Object.entries(site.figures).map(([id, url]) => (
              <li key={id}>
                <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                  {FIGURE_LABEL[id] ?? id.replace(/-/g, ' ')} (SVG)
                </a>
              </li>
            ))}
          </ul>
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
