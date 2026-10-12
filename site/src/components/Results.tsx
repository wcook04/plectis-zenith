// The recorded example, read entirely from the public receipts
// (/api/v1/evidence/window-result and /conditional-result). Nothing measured
// is written into this file.
import { useMemo, useState } from 'react';
import { apiUrl, type Evidence, type Graph } from '../api';
import { nodeName } from '../lib/naming';
import { numberWord } from '../content/copy';

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
import { GraphExplorer } from './graph/GraphExplorer';
import type { RunContext } from './Inspector';
import { RunPicker, type RunChoice } from './RunPicker';

type Call = { completion_tokens?: number; finish_reasons?: string[]; node_id?: string };
type Arm = {
  run_id: string;
  node_id: string;
  status: string;
  native_contract_pass: boolean;
  failure_mode: string;
  calls: Call[];
  output_shape: null | {
    record_counts: Record<string, number>;
    max_subjects: number;
    max_summary_words: number;
    requested_numeric_bounds_met: boolean;
  };
};
type Episode = {
  id: string;
  split: string;
  source_name: string;
  time_anchor: string;
  horizon: string;
  baseline: Arm;
  candidate?: Arm;
};

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }) + ' UTC';

const num = (n: number) => n.toLocaleString('en-GB');

export function Results({
  windowResult,
  conditional,
  labGraph,
  localRuns,
}: {
  windowResult: Evidence;
  conditional: Evidence;
  labGraph: Graph;
  localRuns: boolean;
}) {
  const data = windowResult.data as Record<string, unknown>;
  const results = data.results as Record<string, unknown>;
  const episodes = (results.episodes as Episode[]) ?? [];
  const limit = Number(data.max_output_tokens ?? 0);
  const change = data.change as { node_id: string; before: string; after: string };
  const limitations = (data.limitations as string[]) ?? [];
  const cond = conditional.data as Record<string, unknown>;
  const modes = Object.keys((results.failure_modes as Record<string, unknown>) ?? {});
  const ranOutCount = episodes.filter((e) => e.baseline.calls.some((c) => c.finish_reasons?.includes('length'))).length;
  const allRanOut = ranOutCount === episodes.length;
  const developmentCount = episodes.filter((e) => e.split === 'development').length;
  const stoppedAt = Object.entries((cond.states as Record<string, string>) ?? {}).find(([, state]) => state === 'failure')?.[0];

  return (
    <div className="results">
      <section className="results__block" aria-labelledby="tokens-head">
        <h3 id="tokens-head" className="block-head">
          {modes.length === 1 ? 'One failure mode' : `${capital(numberWord(modes.length))} failure modes`} across {numberWord(episodes.length)} snapshots
        </h3>
        <p className="block-lede">
          {nodeName(change.node_id)} is asked to return one JSON map of where the miners agree and disagree. With the
          response limit fixed at {num(limit)} tokens,{' '}
          {allRanOut ? 'every original attempt ran out before the JSON closed.' : `${numberWord(ranOutCount)} of ${numberWord(episodes.length)} original attempts ran out before the JSON closed.`}
        </p>
        <TokenChart episodes={episodes} limit={limit} />
      </section>

      <section className="results__block" aria-labelledby="change-head">
        <h3 id="change-head" className="block-head">
          The one change
        </h3>
        <p className="block-lede">
          After the {numberWord(developmentCount)} earlier failures were inspected, one passage was added to the replay
          instruction for {nodeName(change.node_id)} and frozen before the later inputs ran. An agent wrote the change;
          all other policy entries stayed identical.
        </p>
        <InstructionDiff before={change.before} after={change.after} />
        <ShapeCheck episodes={episodes} instruction={change.after} />
      </section>

      <section className="results__block results__block--wide" aria-labelledby="cont-head">
        <h3 id="cont-head" className="block-head">
          {stoppedAt ? `The continuation stopped at ${nodeName(stoppedAt)}` : 'Then the next step failed'}
        </h3>
        <p className="block-lede">
          A separate continuation loaded the {numberWord(Object.keys((cond.reused_ancestor_sha256 as object) ?? {}).length)} unchanged
          ancestor outputs from the {fmtDate(String(cond.time_anchor))} run and all{' '}
          {numberWord(Object.keys((cond.frozen_feed_sha256 as object) ?? {}).length)} saved feeds, then ran forward with the
          changed instruction. {String(cond.next_failure ?? '')}
        </p>
        <p className="block-lede">
          The graph below shows each node’s recorded state. Select {nodeName('lab_decide')} to read the failure, or any
          node to compare what ran in this run with what was loaded from the earlier run.
        </p>
        <Continuation conditional={conditional} labGraph={labGraph} localRuns={localRuns} />
      </section>

      <section className="results__block results__limits" aria-labelledby="limits-head">
        <h3 id="limits-head" className="block-head">
          What this does not show
        </h3>
        <ul className="limits">
          {limitations.map((line) => (
            <li key={line}>{line}</li>
          ))}
          <li>{String(cond.interpretation ?? '')}.</li>
        </ul>
        <p className="block-foot">
          {num(Number(data.calls ?? 0))} model calls in the window study, about US$
          {Number(data.actual_cost_usd ?? 0).toFixed(2)} in total.{' '}
          <a href={apiUrl('/api/v1/evidence/window-result')} target="_blank" rel="noreferrer">
            Window experiment record
          </a>
          ,{' '}
          <a href={apiUrl('/api/v1/evidence/conditional-result')} target="_blank" rel="noreferrer">
            continuation record
          </a>
          .
        </p>
      </section>
    </div>
  );
}

function TokenChart({ episodes, limit }: { episodes: Episode[]; limit: number }) {
  const splits = Array.from(new Set(episodes.map((e) => e.split)));
  const splitLabel = (split: string) =>
    split === 'development' ? 'Earlier snapshots, used to choose the change' : 'Later snapshots, change frozen';
  return (
    <figure className="token-chart">
      <table>
        <caption className="visually-hidden">
          Response tokens used by each attempt against the {num(limit)}-token limit
        </caption>
        <colgroup>
          <col className="tc-date" />
          <col className="tc-arm" />
          <col className="tc-plot" />
          <col className="tc-count" />
          <col className="tc-result" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">Snapshot</th>
            <th scope="col">Instruction</th>
            <th scope="col" className="tc-axis">
              <span>0</span>
              <span>{num(limit)}-token limit</span>
            </th>
            <th scope="col" className="tc-num">Tokens</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        {splits.map((split) => (
          <tbody key={split} className="tc-group">
            <tr className="tc-group-head">
              <th colSpan={5} scope="colgroup">
                {splitLabel(split)}
              </th>
            </tr>
            {episodes
              .filter((e) => e.split === split)
              .flatMap((episode) => {
                const arms: Array<{ arm: 'Original' | 'Changed'; data: Arm }> = [{ arm: 'Original', data: episode.baseline }];
                if (episode.candidate) arms.push({ arm: 'Changed', data: episode.candidate });
                return arms.map(({ arm, data }, i) => {
                  const call = data.calls[0] ?? {};
                  const tokens = call.completion_tokens ?? 0;
                  const ranOut = call.finish_reasons?.includes('length');
                  return (
                    <tr key={`${episode.id}-${arm}`} className={i === 0 ? 'tc-first' : 'tc-pair'}>
                      <th scope="row" className="tc-date-cell">
                        {i === 0 ? fmtDate(episode.time_anchor) : <span className="visually-hidden">{fmtDate(episode.time_anchor)}</span>}
                      </th>
                      <td>{arm}</td>
                      <td className="tc-plot-cell">
                        <span className="bar-track">
                          <span
                            className={`bar-fill${arm === 'Changed' ? ' bar-fill--changed' : ''}${ranOut ? ' bar-fill--capped' : ''}`}
                            style={{ width: `${Math.min(100, (tokens / limit) * 100)}%` }}
                          />
                        </span>
                      </td>
                      <td className="tc-num">{num(tokens)}</td>
                      <td className={data.native_contract_pass ? 'is-pass' : 'is-fail'}>
                        {data.native_contract_pass ? 'Valid JSON' : ranOut ? 'Ran out of tokens' : data.failure_mode}
                      </td>
                    </tr>
                  );
                });
              })}
          </tbody>
        ))}
      </table>
      <figcaption>
        Response length of the {nodeName(episodes[0]?.baseline.node_id ?? '')} call on one shared scale. Valid JSON is
        not the same as meeting the requested bounds, shown below, or as completing the forecast. The earlier snapshots
        were not rerun with the change.
      </figcaption>
    </figure>
  );
}

function InstructionDiff({ before, after }: { before: string; after: string }) {
  const appended = after.startsWith(before) ? after.slice(before.length) : null;
  return (
    <div className="diff">
      {appended !== null ? (
        <p className="diff__text">
          <span className="diff__same">{before}</span>
          <ins className="diff__added">{appended}</ins>
        </p>
      ) : (
        <>
          <p className="diff__text">
            <del>{before}</del>
          </p>
          <p className="diff__text">
            <ins className="diff__added">{after}</ins>
          </p>
        </>
      )}
      <p className="diff__key">
        <ins className="diff__added">Marked text</ins> was added; the rest is the unchanged replay instruction.
      </p>
    </div>
  );
}

// The requested bounds are read from the frozen instruction text itself.
function bound(instruction: string, pattern: RegExp): number | null {
  const match = pattern.exec(instruction);
  return match ? Number(match[1]) : null;
}

function Ask({ value, limit, unit }: { value: number; limit: number | null; unit: string }) {
  return (
    <td className={limit === null ? '' : value <= limit ? 'is-pass' : 'is-fail'}>
      {value} {unit}
      {limit !== null && <span className="shape__ask">asked at most {limit}</span>}
    </td>
  );
}

function ShapeCheck({ episodes, instruction }: { episodes: Episode[]; instruction: string }) {
  const changed = episodes.filter((e) => e.candidate?.output_shape);
  if (changed.length === 0) return null;
  const maxRecords = bound(instruction, /at most (\d+) strongest records/i);
  const maxSubjects = bound(instruction, /at most (\d+) subjects/i);
  const maxWords = bound(instruction, /at most (\d+) words/i);
  return (
    <div className="shape">
      <p className="shape__lede">
        Did the changed outputs follow the new limits? They passed the original schema, but not every bound:
      </p>
      <table className="shape__table">
        <thead>
          <tr>
            <th scope="col">Later snapshot</th>
            <th scope="col">Most records in an array</th>
            <th scope="col">Largest record</th>
            <th scope="col">Longest summary</th>
          </tr>
        </thead>
        <tbody>
          {changed.map((episode) => {
            const shape = episode.candidate!.output_shape!;
            const counts = Object.values(shape.record_counts);
            return (
              <tr key={episode.id}>
                <th scope="row">{fmtDate(episode.time_anchor)}</th>
                <Ask value={Math.max(...counts)} limit={maxRecords} unit={Math.max(...counts) === 1 ? 'record' : 'records'} />
                <Ask value={shape.max_subjects} limit={maxSubjects} unit="subjects" />
                <Ask value={shape.max_summary_words} limit={maxWords} unit="words" />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Continuation({ conditional, labGraph, localRuns }: { conditional: Evidence; labGraph: Graph; localRuns: boolean }) {
  const cond = conditional.data as Record<string, unknown>;
  const receipt: RunContext = useMemo(() => {
    const calls: Record<string, Call> = {};
    ((cond.calls as Call[]) ?? []).forEach((call) => {
      if (call.node_id) calls[call.node_id] = call;
    });
    const reused = [
      ...Object.keys((cond.reused_ancestor_sha256 as Record<string, string>) ?? {}),
      ...Object.keys((cond.frozen_feed_sha256 as Record<string, string>) ?? {}),
    ];
    const states: Record<string, string> = { ...((cond.states as Record<string, string>) ?? {}) };
    reused.forEach((id) => {
      if (states[id] === 'success' || states[id] === undefined) states[id] = 'loaded';
    });
    return {
      kind: 'receipt',
      label: 'Published continuation record',
      sourceUrl: apiUrl('/api/v1/evidence/conditional-result'),
      states,
      calls,
      note: `Earlier outputs were loaded from run ${String(cond.source_run_id)} and not computed again.`,
    };
  }, [cond]);

  const [choice, setChoice] = useState<{ value: string; run: RunContext | null }>({ value: 'receipt', run: receipt });
  const [selected, setSelected] = useState<string | null>(null);

  const onChange = (next: RunChoice, value: string) => {
    if (next.kind === 'none') setChoice({ value, run: null });
    else if (next.kind === 'receipt') setChoice({ value, run: receipt });
    else setChoice({ value, run: { kind: 'local', runId: next.summary.run_id, summary: next.summary } });
  };

  return (
    <GraphExplorer
      key={choice.value}
      graph={labGraph}
      title="Lab graph with the continuation's recorded states"
      context={choice.run?.kind === 'receipt' ? 'Lab graph: conditional continuation record' : choice.run?.kind === 'local' ? `Lab graph: saved run ${choice.run.runId}` : 'Lab graph: definitions'}
      run={choice.run}
      initialSelected={selected}
      onSelectionChange={setSelected}
      maxHeight={560}
      runControl={
        <RunPicker
          mission="lab"
          value={choice.value}
          onChange={onChange}
          receiptLabel="Published continuation record"
          localEnabled={localRuns}
        />
      }
    />
  );
}
