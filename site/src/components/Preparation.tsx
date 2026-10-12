// The mixed-data edition's verified preparation, read from
// /api/v1/evidence/demo-result and /sources. Nothing measured is written here.
import { useMemo, useState } from 'react';
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
  return `${Number(d.completed_count ?? 0)} inputs loaded and the ${pending.join(', ') || 'first'} request prepared, using ${Number(d.model_calls ?? 0)} model calls.`;
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
      label: 'Public receipt: preparation',
      sourceUrl: apiUrl('/api/v1/evidence/demo-result'),
      states,
      calls: {},
      note: String(d.claim_boundary ?? ''),
    };
  }, [labGraph, completed, pending, d.claim_boundary]);

  const [choice, setChoice] = useState<{ value: string; run: RunContext | null }>({ value: 'receipt', run: receipt });
  const [selected, setSelected] = useState<string | null>(null);
  const onChange = (next: RunChoice, value: string) => {
    if (next.kind === 'none') setChoice({ value, run: null });
    else if (next.kind === 'receipt') setChoice({ value, run: receipt });
    else setChoice({ value, run: { kind: 'local', runId: next.summary.run_id, summary: next.summary } });
  };

  return (
    <div className="results">
      <section className="results__block" aria-labelledby="prep-head">
        <h3 id="prep-head" className="block-head">
          What the preparation receipt records
        </h3>
        <dl className="ledger">
          <div>
            <dt>Inputs loaded by the native Lab</dt>
            <dd>{completed}</dd>
          </div>
          <div>
            <dt>Request prepared, awaiting a model response</dt>
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
        <blockquote className="boundary">
          <p>{String(d.claim_boundary ?? '')}</p>
          <footer>
            Claim boundary from the{' '}
            <a href={apiUrl('/api/v1/evidence/demo-result')} target="_blank" rel="noreferrer">
              preparation receipt
            </a>
          </footer>
        </blockquote>
      </section>

      {snapshots.length > 0 && (
        <section className="results__block" aria-labelledby="inputs-head">
          <h3 id="inputs-head" className="block-head">
            Which inputs are real
          </h3>
          <p className="block-lede">
            The demonstration uses {numberWord(snapshots.length)} saved snapshots. Real inputs are copied unchanged into
            the computation but kept off the public site; the synthetic ones are published in full and open from the
            feed nodes in the graph.
          </p>
          <table className="shape__table inputs-table">
            <thead>
              <tr>
                <th scope="col">Feed</th>
                <th scope="col">Input</th>
                <th scope="col">On this site</th>
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
                    <td className="inputs-table__payload">{PAYLOAD_LABEL[lane.public_payload ?? ''] ?? lane.public_payload ?? ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="block-foot">
            Snapshots: {snapshots.map((s) => `${s.id}, ${fmtDate(s.as_of)}`).join('; ')}. Synthetic examples are not
            anonymised observations and say nothing about what happened in the historical market.
          </p>
        </section>
      )}

      <section className="results__block results__block--wide" aria-labelledby="prep-graph-head">
        <h3 id="prep-graph-head" className="block-head">
          Where execution stands
        </h3>
        <p className="block-lede">
          The inputs are loaded and {pending.map(nodeName).join(', ') || 'the first step'} has its request prepared. Every
          later node has not started, so there are no model outputs to inspect yet; select a node to read what it would
          receive and produce.
        </p>
        <GraphExplorer
          key={choice.value}
          graph={labGraph}
          title="Lab graph with the preparation receipt's states"
          run={choice.run}
          initialSelected={selected}
          onSelectionChange={setSelected}
          maxHeight={560}
          runControl={
            <RunPicker mission="lab" value={choice.value} onChange={onChange} receiptLabel="Public receipt: preparation" localEnabled={localRuns} />
          }
        />
      </section>
    </div>
  );
}
