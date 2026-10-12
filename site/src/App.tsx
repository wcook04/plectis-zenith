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
import { SiteEvidenceContext } from './lib/siteContext';
import { Preparation, preparationSummary } from './components/Preparation';
import { nodeName } from './lib/naming';
import { useAsync } from './lib/hooks';
import { ThemeToggle } from './components/ThemeToggle';

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

function Shell({ children, site }: { children: React.ReactNode; site?: Site }) {
  const [noticeOpen, setNoticeOpen] = useState(false);
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <div className="notice-bar">
          <div className="wrap notice-bar__inner">
            <p>
              <strong>{site?.notice ?? 'This is not financial advice.'}</strong>
              <span className="notice-bar__extra"> Zenith is an experimental research prototype.</span>
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
                <a key={chapter.id} href={`#${chapter.id}`}>
                  {NAV_LABEL[chapter.id] ?? chapter.title}
                </a>
              ))}
              <a href="#paper">Paper</a>
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
          <p>The notice could not be loaded. This is not financial advice.</p>
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
  const lab = useGraph(byId.get('lab')?.graph_url ?? '/api/v1/graph?mission=lab');
  const deepLink = useMemo(() => new URLSearchParams(window.location.search).get('node'), []);
  const byline = useByline(site);

  return (
    <SiteEvidenceContext.Provider value={site.evidence}>
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
            Open the Lab graph
          </a>
          {byline && <span className="hero__byline">{byline}</span>}
        </div>
        </div>
        <nav className="hero__map" aria-label="What each chapter shows">
          <p className="hero__map-head">What each part of the site shows</p>
          <ol>
            {site.chapters.map((chapter) => (
              <li key={chapter.id} className={`map-row map-row--${chapter.evidence_kind}`}>
                <a href={`#${chapter.id}`}>
                  <span className="map-row__title">{chapter.title}</span>
                  <span className="map-row__kind">{EVIDENCE_KIND_LABEL[chapter.evidence_kind]?.label ?? chapter.evidence_kind}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </section>
      <StatusStrip site={site} />

      {site.chapters.map((chapter, index) => (
        <ChapterSection
          key={chapter.id}
          chapter={chapter}
          index={index}
          paper={paper}
          paragraphs={
            chapter.id === 'lab'
              ? labParagraphs(lab.status === 'ready' && lab.value ? graphFacts(lab.value) : null)
              : CHAPTER_COPY[`${chapter.id}:${chapter.evidence_kind}`]?.paragraphs
          }
        >
          {chapter.id === 'idea' && <LoopDiagram />}
          {chapter.id === 'lab' && (
            <LabFigure site={site} graph={lab.status === 'ready' ? lab.value : null} deepLink={deepLink} />
          )}
          {chapter.id === 'oracle' && <OracleFigure chapter={chapter} />}
          {chapter.id === 'evolve' && <EvolveFigure chapter={chapter} />}
          {chapter.id === 'results' && (
            <ResultsFigure chapter={chapter} labGraph={lab.status === 'ready' ? lab.value : null} site={site} />
          )}
          {chapter.id === 'next' && <NextFigure chapter={chapter} />}
        </ChapterSection>
      ))}

      <PaperSection site={site} paper={paper} />
      <footer className="footer">
        <div className="wrap footer__inner">
          <p>
            <strong>This is not financial advice.</strong> Historical examples and model outputs are not investment
            recommendations and must not be used to make financial decisions.
          </p>
          <p>
            <a href="https://github.com/wcook04/plectis-zenith" target="_blank" rel="noreferrer">
              Source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </Shell>
    </SiteEvidenceContext.Provider>
  );
}

// One line under the hero with where the work actually stands, read from the
// receipt bound to the results chapter.
function StatusStrip({ site }: { site: Site }) {
  const chapter = site.chapters.find((c) => c.evidence_kind === 'measured_execution' || c.evidence_kind === 'verified_preparation');
  const url = chapter?.evidence_urls[0];
  const evidence = useAsync<Evidence | null>(() => (url ? api.evidence(url) : Promise.resolve(null)), [url]);
  if (!chapter) return null;
  let summary: string | null = null;
  if (evidence.status === 'ready' && evidence.value) {
    const schema = String(evidence.value.data.schema ?? '');
    if (schema.startsWith('zenith_demo_preparation')) summary = preparationSummary(evidence.value);
    else if (schema.startsWith('zenith_original_feed_window')) summary = windowSummary(evidence.value);
  }
  return (
    <section className="status-strip" aria-label="Current status">
      <div className="wrap status-strip__inner">
        <p>
          <strong>Where it stands.</strong> {summary ?? 'The full loop has not run end to end.'}
          {site.data_note && <span className="status-strip__note"> {site.data_note}</span>}
        </p>
        <a href={`#${chapter.id}`}>{chapter.title}</a>
      </div>
    </section>
  );
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
    acquired: feeds.filter((n) => n.lane !== 'CALCULATOR').sort((a, b) => laneIndex(a.lane) - laneIndex(b.lane)).map((n) => laneName(n.lane)),
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
  paragraphs,
  children,
}: {
  chapter: Chapter;
  index: number;
  paper: Paper | null;
  paragraphs?: string[];
  children: React.ReactNode;
}) {
  const copy = CHAPTER_COPY[chapter.id];
  return (
    <section className={`chapter chapter--${chapter.id}`} id={chapter.id} aria-labelledby={`${chapter.id}-title`}>
      <div className="wrap chapter__grid">
        <div className="chapter__text">
          <h2 id={`${chapter.id}-title`}>
            <span className="chapter__num" aria-hidden="true">{index + 1}</span>
            {chapter.title}
          </h2>
          {(paragraphs ?? copy?.paragraphs)?.map((p) => <p key={p}>{p}</p>)}
        </div>
        <PaperAside chapter={chapter} paper={paper} />
      </div>
      <div className="wrap chapter__figure">{children}</div>
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
        <GraphExplorer graph={graph.value} title="The Oracle graph" maxHeight={640} />
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
          <GraphExplorer graph={graph.value} title="The Evolve graph" maxHeight={320} />
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
          <h3>Showing it helps</h3>
          <p>Run the original and the revision on later cases nobody used to choose it, scored by a rule fixed in advance.</p>
          <p className="contrast__state">Requires a separate comparison</p>
        </div>
      </div>
    </div>
  );
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
  if (isPreparation && labGraph && kind.status === 'ready' && kind.value) {
    return (
      <>
        <p className="model-notice">
          <strong>This is not financial advice.</strong> The demonstration mixes real saved market data with invented
          examples. Nothing below is a prediction or a recommendation.
        </p>
        <Preparation result={kind.value} sources={sources.status === 'ready' ? sources.value : null} labGraph={labGraph} localRuns={site.local_runs_enabled} />
      </>
    );
  }
  if (evidence.status === 'error') {
    return (
      <div className="model-notice">
        <p>
          <strong>The measured-result receipts are not available from this server</strong> ({evidence.message}). The
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
    return <p className="inspector__warn">The result receipt could not be loaded: {kind.message}</p>;
  }
  if (evidence.status === 'loading' || kind.status === 'loading' || !labGraph || !evidence.value) return <Loading what="the recorded results" />;
  return (
    <>
      <p className="model-notice">
        <strong>This is not financial advice.</strong> The runs below used historical market data. Their outputs are
        research records, not recommendations.
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
            <p className="paper-band__hash">
              PDF SHA-256 <code className="hash">{paper.pdf_sha256}</code>
              <br />
              <a href={paper.source.url} target="_blank" rel="noreferrer">
                LaTeX source
              </a>
            </p>
          )}
          <h3 className="paper-aside__head">Receipts</h3>
          <ul className="plain-list">
            {Object.entries(site.evidence).map(([id, url]) => (
              <li key={id}>
                <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                  {id.replace(/-/g, ' ')}
                </a>
              </li>
            ))}
          </ul>
          <h3 className="paper-aside__head">Diagrams from the repository</h3>
          <ul className="plain-list">
            {Object.entries(site.figures).map(([id, url]) => (
              <li key={id}>
                <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                  {id.replace(/-/g, ' ')} (SVG)
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
                <li key={citation.id}>
                  {latexToText(citation.latex)}
                  {citation.urls.map((url) => (
                    <a key={url} className="refs__link" href={url} target="_blank" rel="noreferrer">
                      {linkLabel(url)}
                    </a>
                  ))}
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
