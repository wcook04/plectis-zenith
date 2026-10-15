// The synthetic observed-system edition's verified preparation, read from
// /api/v1/evidence/demo-result and /sources. Nothing measured is written here.
import { useMemo, useRef, useState } from 'react';
import { apiUrl, type Evidence, type Graph } from '../api';
import { laneLabel } from '../lib/lanes';
import { nodeName } from '../lib/naming';
import { ORIGIN_LABEL, PAYLOAD_LABEL } from '../lib/provenance';
import { numberWord } from '../content/copy';
import { GraphExplorer } from './graph/GraphExplorer';
import type { RunContext } from './Inspector';
import { RunPicker, type RunChoice } from './RunPicker';

type Lane = { node_id: string; input_origin: string; public_payload?: string };
type Snapshot = { id: string; as_of: string; lanes: Lane[] };

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) +
  ' UTC';

export function preparationSummary(result: Evidence): string {
  const d = result.data as Record<string, unknown>;
  const pending = ((d.pending_nodes as string[]) ?? []).map(nodeName);
  const calls = Number(d.model_calls ?? 0);
  const loaded = numberWord(Number(d.completed_count ?? 0));
  const first = pending.join(', ') || 'the first reasoning step';
  const model = calls === 0 ? 'No language model has been called' : `The language model has been called ${numberWord(calls)} times`;
  return `The Lab has loaded its ${loaded} inputs and written the request for its first step, ${first}. ${model}${d.forecast_complete ? '.' : ', so no forecast exists.'}`;
}

export function Preparation({
  result,
  sources,
  labGraph,
  localRuns,
}: {
  result: Evidence;
  sources: Evidence | null;
  labGraph: Graph;
  localRuns: boolean;
}) {
  const d = result.data as Record<string, unknown>;
  const pending = (d.pending_nodes as string[]) ?? [];
  const completed = Number(d.completed_count ?? 0);
  const snapshots = ((sources?.data.snapshots as Snapshot[]) ?? []).filter((s) => Array.isArray(s.lanes));

  const receipt: RunContext = useMemo(() => {
    const feeds = labGraph.nodes.filter((n) => n.group === 'feeds');
    const states: Record<string, string> = {};
    labGraph.nodes.forEach((n) => (states[n.id] = 'not_started'));
    // The receipt counts loaded inputs; mark the feed nodes only when the count
    // matches them exactly, otherwise leave them as "no record".
    feeds.forEach((n) => (states[n.id] = feeds.length === completed ? 'loaded' : 'unknown'));
    pending.forEach((id) => (states[id] = 'pending'));
    return {
      kind: 'receipt',
      label: 'Published preparation record',
      sourceUrl: apiUrl('/api/v1/evidence/demo-result'),
      states,
      calls: {},
      note: String(d.claim_boundary ?? ''),
    };
  }, [labGraph, completed, pending, d.claim_boundary]);

  const [choice, setChoice] = useState<{ value: string; run: RunContext | null }>({ value: 'receipt', run: receipt });
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ id: string; nonce: number } | null>(null);
  const graphRef = useRef<HTMLDivElement>(null);
  const inspect = (id: string) => {
    setFocus((prev) => ({ id, nonce: (prev?.nonce ?? 0) + 1 }));
    graphRef.current?.scrollIntoView({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  };
  const onChange = (next: RunChoice, value: string) => {
    if (next.kind === 'none') setChoice({ value, run: null });
    else if (next.kind === 'receipt') setChoice({ value, run: receipt });
    else setChoice({ value, run: { kind: 'local', runId: next.summary.run_id, summary: next.summary } });
  };

  return (
    <div className="results">
      <section className="results__block" aria-labelledby="prep-head">
        <h3 id="prep-head" className="block-head">
          Contents of the preparation record
        </h3>
        <dl className="ledger">
          <div>
            <dt>Inputs loaded</dt>
            <dd>{completed}</dd>
          </div>
          <div>
            <dt>Prepared request</dt>
            <dd>{pending.map(nodeName).join(', ') || 'none'}</dd>
          </div>
          <div>
            <dt>Model calls</dt>
            <dd>{Number(d.model_calls ?? 0)}</dd>
          </div>
          <div>
            <dt>Forecast completed</dt>
            <dd>{d.forecast_complete ? 'Yes' : 'No'}</dd>
          </div>
        </dl>
        <div className="boundary">
          <p>
            The record claims only that the inputs were loaded and the first request was prepared. It makes no claim
            that predictions, diagnoses or revisions are correct.
          </p>
          <p className="boundary__source">
            <a href={apiUrl('/api/v1/evidence/demo-result')} target="_blank" rel="noreferrer">
              Read the preparation record (JSON)
            </a>
          </p>
        </div>
      </section>

      {snapshots.length > 0 && (
        <section className="results__block" aria-labelledby="inputs-head">
          <h3 id="inputs-head" className="block-head">
            Where the input data came from
          </h3>
          <p className="block-lede">
            The demonstration contains invented observations saved at {numberWord(snapshots.length)} times. The five data sources
            and the summaries calculated from them are published in full. Select a data source below or in the diagram to read it.
          </p>
          <table className="shape__table inputs-table">
            <thead>
              <tr>
                <th scope="col">Data source</th>
                <th scope="col">Origin</th>
                <th scope="col">Public availability</th>
              </tr>
            </thead>
            <tbody>
              {snapshots[0].lanes.map((lane) => {
                const node = labGraph.nodes.find((n) => n.id === lane.node_id);
                return (
                  <tr key={lane.node_id}>
                    <th scope="row">{node ? laneLabel(node.lane) : nodeName(lane.node_id)}</th>
                    <td>
                      <span className={`z-origin z-origin--${lane.input_origin}`}>{ORIGIN_LABEL[lane.input_origin] ?? lane.input_origin}</span>
                    </td>
                    <td className="inputs-table__payload">
                      {PAYLOAD_LABEL[lane.public_payload ?? ''] ?? lane.public_payload ?? ''}
                      {lane.public_payload === 'included' && node && (
                        <>
                          {' '}
                          <button type="button" className="z-link-button" onClick={() => inspect(lane.node_id)}>
                            Read the synthetic data
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="block-foot">
            Snapshots: {snapshots.map((s) => `${s.id}, ${fmtDate(s.as_of)}`).join('; ')}. Synthetic examples are not
            measurements of a real system or evidence that the graph predicts it accurately.
          </p>
        </section>
      )}

      <section className="results__block results__block--wide" aria-labelledby="prep-graph-head" ref={graphRef}>
        <h3 id="prep-graph-head" className="block-head">
          What has run so far
        </h3>
        <p className="block-lede">
          The inputs are loaded and the request for {pending.map(nodeName).join(', ') || 'the first step'} is prepared. No
          later node has started, so the graph contains no model outputs. Selecting a node shows its instruction, its
          declared inputs and its expected output.
        </p>
        <GraphExplorer
          key={choice.value}
          graph={labGraph}
          title="Lab graph with the preparation receipt's states"
          context={
            choice.run?.kind === 'receipt'
              ? 'Lab graph: preparation record'
              : choice.run?.kind === 'local'
                ? `Lab graph: saved run ${choice.run.runId}`
                : 'Lab graph: definitions'
          }
          focusRequest={focus}
          run={choice.run}
          initialSelected={selected}
          onSelectionChange={setSelected}
          maxHeight={560}
          runControl={
            <RunPicker mission="lab" value={choice.value} onChange={onChange} receiptLabel="Published preparation record" localEnabled={localRuns} />
          }
        />
      </section>
    </div>
  );
}
