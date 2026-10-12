// Node inspector. Adapted from the original Zenith NodeHUD (metadata tab,
// instruction disclosure, dependency chips that navigate) and ArtifactViewer
// (recorded output, failure banner, copy control). Store and endpoint
// dependencies are replaced by the read-only website API, and the inspector
// keeps three things apart that the original could blur: the current authored
// instruction, upstream artifacts a run recorded, and the prompt it saved.
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type Graph, type GraphNode, type RunNode, type RunSummary } from '../api';
import { laneColor, laneLabel } from '../lib/lanes';
import { nodeName } from '../lib/naming';
import { normalizeState, STATE_DESCRIPTION, STATE_LABEL, type NodeState } from '../lib/status';
import { CopyButton } from './CopyButton';
import { JsonView } from './JsonView';
import { ORIGIN_DESCRIPTION, PAYLOAD_LABEL, originLabel } from '../lib/provenance';
import { useSiteEvidence } from '../lib/siteContext';
import { useAsync } from '../lib/hooks';

export type ReceiptCall = { completion_tokens?: number; finish_reasons?: string[] };

export type RunContext =
  | { kind: 'local'; runId: string; summary: RunSummary }
  | {
      kind: 'receipt';
      label: string;
      sourceUrl: string;
      states: Record<string, string>;
      calls: Record<string, ReceiptCall>;
      note: string;
    };

type Props = {
  graph: Graph;
  nodeId: string;
  run: RunContext | null;
  onNavigate: (id: string) => void;
  onClose: () => void;
};

export function Inspector({ graph, nodeId, run, onNavigate, onClose }: Props) {
  const fromGraph = useMemo(() => graph.nodes.find((n) => n.id === nodeId) ?? null, [graph, nodeId]);
  const [detail, setDetail] = useState<{ id: string; node: GraphNode } | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  // Saved local runs open on their record; public receipts carry only a state,
  // so they open on the definition and its data.
  const [tab, setTab] = useState<'definition' | 'run'>(run?.kind === 'local' ? 'run' : 'definition');
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let live = true;
    setDetailError(null);
    api
      .node(nodeId)
      .then((node) => live && setDetail({ id: nodeId, node }))
      .catch((error: Error) => live && setDetailError(error.message));
    return () => {
      live = false;
    };
  }, [nodeId]);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, [nodeId]);

  useEffect(() => {
    if (!run) setTab('definition');
  }, [run]);

  const node = detail?.id === nodeId ? detail.node : fromGraph;
  if (!node) {
    return (
      <aside className="inspector" aria-label="Node details">
        <p className="inspector__empty">This node is not in the current graph.</p>
      </aside>
    );
  }

  const kind = node.type === 'tool' ? 'Tool' : 'Model call';
  return (
    <aside
      className="inspector"
      aria-label={`Details for ${nodeName(node.id)}`}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <header className="inspector__head" style={{ ['--lane' as string]: laneColor(node.lane) }}>
        <div className="inspector__meta">
          <span className="z-node__lane">
            <span className="z-dot" aria-hidden="true" />
            {laneLabel(node.lane)}
          </span>
          <span>{kind}</span>
        </div>
        <h3 ref={headingRef} tabIndex={-1} className="inspector__title">
          {nodeName(node.id)}
        </h3>
        <code className="inspector__id">{node.id}</code>
        <button type="button" className="inspector__close" onClick={onClose} aria-label="Close details">
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {run && (
        <div className="inspector__tabs" role="tablist" aria-label="Inspector views">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'definition'}
            className="inspector__tab"
            onClick={() => setTab('definition')}
          >
            Definition
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'run'}
            className="inspector__tab"
            onClick={() => setTab('run')}
          >
            Run record
          </button>
        </div>
      )}

      <div className="inspector__body">
        {tab === 'run' && run ? (
          <RunRecord key={`${run.kind === 'local' ? run.runId : run.label}|${node.id}`} run={run} node={node} onNavigate={onNavigate} />
        ) : (
          <Definition node={node} graph={graph} onNavigate={onNavigate} detailError={detailError} />
        )}
      </div>
    </aside>
  );
}

function NodeLinks({ ids, graph, onNavigate }: { ids: string[]; graph: Graph; onNavigate: (id: string) => void }) {
  if (ids.length === 0) return <p className="inspector__quiet">None.</p>;
  const inGraph = new Set(graph.nodes.map((n) => n.id));
  return (
    <ul className="node-links">
      {ids.map((id) => {
        const lane = graph.nodes.find((n) => n.id === id)?.lane ?? 'SPINE';
        return (
          <li key={id}>
            {inGraph.has(id) ? (
              <button
                type="button"
                className="node-link"
                style={{ ['--lane' as string]: laneColor(lane) }}
                onClick={() => onNavigate(id)}
              >
                <span className="z-dot" aria-hidden="true" />
                {nodeName(id)}
              </button>
            ) : (
              <span className="node-link node-link--outside">
                {nodeName(id)} <span className="inspector__quiet">(outside this mission)</span>
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Definition({
  node,
  graph,
  onNavigate,
  detailError,
}: {
  node: GraphNode;
  graph: Graph;
  onNavigate: (id: string) => void;
  detailError: string | null;
}) {
  const [open, setOpen] = useState(false);
  const lines = node.instruction.split('\n').length;
  return (
    <>
      <section className="inspector__section">
        <h4>Purpose</h4>
        <p>{node.purpose}</p>
        {node.boundary && (
          <p className="inspector__boundary">
            <span>Boundary.</span> {node.boundary}
          </p>
        )}
      </section>

      {node.demo_provenance && <ProvenanceSection node={node} />}

      <div className="inspector__io">
        <section className="inspector__section">
          <h4>Reads</h4>
          <NodeLinks ids={node.dependencies} graph={graph} onNavigate={onNavigate} />
        </section>
        <section className="inspector__section">
          <h4>Feeds into</h4>
          <NodeLinks ids={node.consumers} graph={graph} onNavigate={onNavigate} />
        </section>
      </div>

      <section className="inspector__section">
        <h4>Expected output</h4>
        <p>{node.expectation}</p>
        <p className="inspector__quiet">
          Output format: <code>{node.output_schema}</code>
        </p>
      </section>

      <section className="inspector__section">
        <div className="inspector__row">
          <h4>Current instruction</h4>
          <CopyButton text={node.instruction} label="Copy instruction" />
        </div>
        <p className="inspector__quiet">
          The authored text in the repository today. A past run may have used a different prompt; open a run
          record to see what it saved.
        </p>
        <pre className={`z-pre inspector__instruction${open ? ' is-open' : ''}`} tabIndex={0}>
          {node.instruction}
        </pre>
        {lines > 14 && (
          <button type="button" className="z-link-button" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? 'Show less' : `Show all ${lines} lines`}
          </button>
        )}
      </section>

      {node.dossier && (
        <section className="inspector__section">
          <h4>Feed dossier</h4>
          <p className="inspector__quiet">The perspective, evidence rules and limits used by this lane.</p>
          <JsonView label="Dossier" value={node.dossier.data} />
          <a href={node.dossier.source.url} target="_blank" rel="noreferrer">Dossier source</a>
        </section>
      )}

      <details className="inspector__section inspector__provenance">
        <summary>Source and provenance</summary>
        <dl>
          <dt>Defined in</dt>
          <dd>
            <a href={node.source.url} target="_blank" rel="noreferrer">
              {node.source.path}
            </a>
          </dd>
          <dt>SHA-256</dt>
          <dd>
            <code className="hash">{node.source.sha256}</code>
          </dd>
          <dt>Mechanism</dt>
          <dd>{node.mechanism}</dd>
          <dt>Instruction status</dt>
          <dd>{node.instruction_kind.replace(/_/g, ' ')}</dd>
        </dl>
        {detailError && <p className="inspector__warn">Live node detail unavailable ({detailError}); showing the graph copy.</p>}
      </details>
    </>
  );
}

type Loaded = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; record: RunNode };

function RunRecord({ run, node, onNavigate }: { run: RunContext; node: GraphNode; onNavigate: (id: string) => void }) {
  if (run.kind === 'receipt') return <ReceiptRecord run={run} node={node} />;
  return <LocalRecord runId={run.runId} summary={run.summary} node={node} onNavigate={onNavigate} />;
}

function StateBlock({ state, title }: { state: NodeState; title: string }) {
  return (
    <div className={`state-block is-${state}`}>
      <span className={`z-state z-state--${state}`}>
        <span className="z-state__glyph" aria-hidden="true" />
        {STATE_LABEL[state]}
      </span>
      <span className="state-block__title">{title}</span>
      <p>{STATE_DESCRIPTION[state]}</p>
    </div>
  );
}

function ReceiptRecord({ run, node }: { run: Extract<RunContext, { kind: 'receipt' }>; node: GraphNode }) {
  const raw = run.states[node.id];
  const state = normalizeState(raw);
  const call = run.calls[node.id];
  return (
    <>
      <StateBlock state={state} title={run.label} />
      {call && (
        <section className="inspector__section">
          <h4>Recorded model call</h4>
          <dl className="facts">
            <dt>Response length</dt>
            <dd>{call.completion_tokens?.toLocaleString('en-GB') ?? 'not recorded'} tokens</dd>
            <dt>Finish reason</dt>
            <dd>
              {(call.finish_reasons ?? []).join(', ') || 'not recorded'}
              {call.finish_reasons?.includes('length') && ' (ran out of response tokens)'}
            </dd>
          </dl>
        </section>
      )}
      <p className="inspector__quiet">{run.note}</p>
      <p className="inspector__quiet">
        Published records give each node’s state and a summary of any model call. They do not include outputs or prompts.{' '}
        <a href={run.sourceUrl} target="_blank" rel="noreferrer">
          Open the record
        </a>
        .
      </p>
    </>
  );
}

function LocalRecord({
  runId,
  summary,
  node,
  onNavigate,
}: {
  runId: string;
  summary: RunSummary;
  node: GraphNode;
  onNavigate: (id: string) => void;
}) {
  const [loaded, setLoaded] = useState<{ key: string; value: Loaded }>({ key: '', value: { status: 'loading' } });
  const key = `${runId}|${node.id}`;

  useEffect(() => {
    let live = true;
    setLoaded({ key, value: { status: 'loading' } });
    api
      .runNode(runId, node.id)
      .then((record) => live && setLoaded({ key, value: { status: 'ready', record } }))
      .catch((error: Error) => live && setLoaded({ key, value: { status: 'error', message: error.message } }));
    return () => {
      live = false;
    };
  }, [key, runId, node.id]);

  // Never show another node's or run's evidence while the next one loads.
  const value: Loaded = loaded.key === key ? loaded.value : { status: 'loading' };
  const outcome = normalizeState(summary.node_outcomes[node.id]);

  if (value.status === 'loading') {
    return (
      <>
        <StateBlock state={outcome} title={`Run ${runId}`} />
        <p className="inspector__quiet" role="status">
          Loading the saved record…
        </p>
      </>
    );
  }
  if (value.status === 'error') {
    return (
      <>
        <StateBlock state={outcome} title={`Run ${runId}`} />
        <p className="inspector__warn" role="alert">
          The saved record could not be read: {value.message}
        </p>
      </>
    );
  }

  const record = value.record;
  const state = normalizeState(record.status);
  const artifact = record.artifact;
  const meta = artifact?.metadata ?? {};
  const failureData =
    artifact?.data && typeof artifact.data === 'object' && !Array.isArray(artifact.data)
      ? (artifact.data as Record<string, unknown>)
      : null;
  const isFailureEnvelope = state === 'failure' && failureData && 'attempt_log' in failureData;

  return (
    <>
      <StateBlock state={state} title={`Run ${record.run_id}`} />
      <dl className="facts">
        <dt>Type of run</dt>
        <dd>{record.source_kind.replace(/_/g, ' ')}</dd>
        {record.subject_run && (
          <>
            <dt>Loads earlier outputs from</dt>
            <dd>
              <code>{record.subject_run}</code>
            </dd>
          </>
        )}
        <dt>Saved output</dt>
        <dd>
          {record.artifact_error
            ? ARTIFACT_ERROR[record.artifact_error] ?? `unavailable (${record.artifact_error})`
            : record.artifact_omitted
              ? 'omitted from this response'
              : `${artifact?.status ?? 'unknown'}, ${(record.artifact_bytes ?? 0).toLocaleString('en-GB')} bytes`}
        </dd>
        {meta.hydrated_from && (
          <>
            <dt>Loaded from</dt>
            <dd>
              <code>{meta.hydrated_from}</code>
            </dd>
          </>
        )}
      </dl>

      {meta.error && (
        <div className="failure-banner" role="note">
          <strong>Recorded error.</strong> {meta.error}
        </div>
      )}

      {meta.input_node_ids && meta.input_node_ids.length > 0 && (
        <section className="inspector__section">
          <h4>Earlier outputs given to this node</h4>
          <p className="inspector__quiet">
            This list shows which earlier outputs the node received. It is not the exact text sent to the model.
          </p>
          <ul className="node-links node-links--wrap">
            {meta.input_node_ids.map((id) => (
              <li key={id}>
                <button type="button" className="node-link" onClick={() => onNavigate(id)}>
                  {nodeName(id)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {artifact && artifact.data !== undefined && !isFailureEnvelope && (
        <section className="inspector__section">
          <JsonView value={artifact.data} label={state === 'loaded' ? 'Loaded output' : 'Recorded output'} />
        </section>
      )}

      {isFailureEnvelope && failureData && (
        <section className="inspector__section">
          <h4>Last invalid output</h4>
          <p className="inspector__quiet">The response the validator rejected, as saved.</p>
          <pre className="z-pre z-pre--short">{String(failureData.last_invalid_output ?? '')}</pre>
        </section>
      )}

      {record.attempts.length > 0 && (
        <section className="inspector__section">
          <h4>Recorded attempts</h4>
          {record.attempts.map((attempt) => (
            <article key={attempt.attempt} className="attempt">
              <header>
                Attempt {attempt.attempt}: {attempt.status}
                {attempt.error_class ? `, ${attempt.error_class.replace(/_/g, ' ').toLowerCase()}` : ''}
              </header>
              {attempt.errors?.map((error, index) => (
                <p key={index} className="attempt__error">
                  {error}
                </p>
              ))}
              {attempt.prompt_snippet !== undefined && (
                <Excerpt
                  title="Recorded prompt excerpt"
                  text={attempt.prompt_snippet}
                  total={attempt.prompt_length}
                  truncated={Boolean(attempt.prompt_truncated) || attempt.prompt_snippet.startsWith('[TRUNCATED')}
                  hash={attempt.prompt_sha256}
                />
              )}
              {attempt.output_text !== undefined && (
                <Excerpt
                  title="Recorded model output"
                  text={attempt.output_text}
                  total={attempt.output_length}
                  truncated={Boolean(attempt.output_truncated)}
                />
              )}
            </article>
          ))}
        </section>
      )}
    </>
  );
}

const ARTIFACT_ERROR: Record<string, string> = {
  missing: 'none saved (this means no output, not a success)',
  malformed: 'saved but unreadable',
  unsafe: 'withheld because its file path is unsafe',
  oversized: 'larger than the 8 MiB limit, so not loaded',
};

function Excerpt({
  title,
  text,
  total,
  truncated,
  hash,
}: {
  title: string;
  text: string;
  total?: number;
  truncated: boolean;
  hash?: string;
}) {
  return (
    <div className="excerpt">
      <div className="excerpt__head">
        <span>{title}</span>
        <span className="inspector__quiet">
          {total !== undefined && `${total.toLocaleString('en-GB')} characters`}
          {truncated && <strong className="flag">, excerpt only</strong>}
        </span>
        <CopyButton text={text} label="Copy" />
      </div>
      <pre className="z-pre z-pre--short">{text}</pre>
      {hash && (
        <p className="inspector__quiet">
          SHA-256 <code className="hash">{hash}</code>
        </p>
      )}
    </div>
  );
}

function ProvenanceSection({ node }: { node: GraphNode }) {
  const p = node.demo_provenance!;
  const evidence = useSiteEvidence();
  const synthetic = p.input_origin === 'authored_synthetic';
  const replacementsUrl = synthetic ? evidence.replacements : undefined;
  const replacements = useAsync(
    () => (replacementsUrl ? api.evidence(replacementsUrl) : Promise.resolve(null)),
    [replacementsUrl],
  );
  const snapshots =
    replacements.status === 'ready' && replacements.value
      ? ((replacements.value.data.snapshots as Array<{ id: string; as_of: string; artifacts: Record<string, { data?: unknown }> }>) ?? [])
          .map((snap) => ({ id: snap.id, asOf: snap.as_of, data: snap.artifacts?.[node.id]?.data }))
          .filter((snap) => snap.data !== undefined)
      : [];
  return (
    <section className={`inspector__section provenance provenance--${p.input_origin}`}>
      <h4>Data used in this demonstration</h4>
      <p>
        <span className={`z-origin z-origin--${p.input_origin}`}>{originLabel(p)}</span>{' '}
        {ORIGIN_DESCRIPTION[p.input_origin] ?? ''}
      </p>
      {p.public_payload && <p className="inspector__quiet">{PAYLOAD_LABEL[p.public_payload] ?? p.public_payload.replace(/_/g, ' ')}.</p>}
      {p.dependencies && p.dependencies.length > 0 && (
        <p className="inspector__quiet">Computed from {p.dependencies.map(nodeName).join(', ')}.</p>
      )}
      {snapshots.map((snap) => (
        <div key={snap.id} className="provenance__payload">
          <JsonView value={snap.data} label={`Synthetic ${snap.id} snapshot, ${new Date(snap.asOf).toLocaleString('en-GB', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC`} />
        </div>
      ))}
      <details className="provenance__hashes">
        <summary>Hashes</summary>
        <dl className="facts">
          {p.input_sha256 && (
            <>
              <dt>Input SHA-256</dt>
              <dd><code className="hash">{p.input_sha256}</code></dd>
            </>
          )}
          {p.source_sha256 && (
            <>
              <dt>Source SHA-256</dt>
              <dd><code className="hash">{p.source_sha256}</code></dd>
            </>
          )}
        </dl>
      </details>
    </section>
  );
}
