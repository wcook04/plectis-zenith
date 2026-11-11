// The front page: the kept-experience study. Every figure is read from
// content/keptExperience.json, which scripts/build_kept_experience_site_data.py
// writes from the study's saved records at a fixed revision. The page needs no
// request to the data server, so it is complete on first paint.
import { useEffect, useMemo, useRef, useState } from 'react';
import study from '../content/keptExperience.json';
import { FAMILY, clock, isReleased, spokenDuration } from '../content/family';
import { FamilyLockup, FamilySites, ZenithMark } from './Family';
import { ThemeToggle } from './ThemeToggle';
import { CopyButton } from './CopyButton';

type Row = {
  arm: string;
  mean: number;
  diff_vs_none?: number;
  ci95?: number[];
  wins?: number;
  losses?: number;
  ties?: number;
  sign_p?: number;
  all_inputs_valid_subset?: { problems: number; diff_vs_none: number; ci95: number[] };
};

const REPO = 'https://github.com/wcook04/plectis-zenith';
const BLOB = `${REPO}/blob/${study.revision}`;
const TREE = `${REPO}/tree/${study.revision}`;
export const STUDY_REPORT = `${BLOB}/docs/studies/kept-experience/README.md`;
const PROTOCOL = `${BLOB}/docs/studies/kept-experience/protocol.md`;
const RESULTS = `${BLOB}/docs/studies/kept-experience/results.json`;
const RECORD = `${BLOB}/docs/studies/kept-experience/frozen/experience.md`;
const EVIDENCE = `${TREE}/examples/kept-experience`;
const scoreFile = (arm: string) => `${BLOB}/examples/kept-experience/scores/${arm}__heldout__natural.json`;
const REPLAY = 'python scripts/replay_kept_experience.py replay /path/to/HumanEvalPlus.jsonl';
export const EARLIER_HREF = '?studies=earlier';

const ARM_LABEL: Record<string, string> = {
  cold: 'Nothing',
  advice: 'Generic testing advice',
  kept: 'Practice record',
  lessons_v1: 'Rules v1, written by the tester',
  lessons_v2: 'Rules v2, revised on development misses',
  imagine: 'Imagined faults',
  imagine_kept: 'Imagined faults and the record',
  random_plus: 'Five random EvalPlus inputs, no model',
};

/**
 * Tenths of a percentage point from a four-decimal share, rounded half away
 * from zero as the study report prints them (-0.0315 -> 3.2, 0.0785 -> 7.9).
 * toFixed(6) first removes binary noise such as 31.499999999999996.
 */
function tenths(value: number): string {
  return (Math.round(Number((Math.abs(value) * 1000).toFixed(6))) / 10).toFixed(1);
}

/** 0.6917 -> "69.2%". */
export function pct(value: number): string {
  return `${tenths(value)}%`;
}

/** 0.0785 -> "+7.9", -0.0342 -> "−3.4" (a real minus sign). */
export function points(value: number): string {
  return `${value < 0 ? '−' : '+'}${tenths(value)}`;
}

const interval = (ci: number[]) => `${points(ci[0])} to ${points(ci[1])}`;

const primary = study.results.primary.rows as Row[];
const byArm = new Map(primary.map(row => [row.arm, row]));
const none = byArm.get('cold')!;
const record = byArm.get('kept')!;
const noTimeout = new Map((study.results.exploratory_without_timeout_exposures.rows as Row[]).map(row => [row.arm, row]));
const reasoningOff = new Map((study.results.experiment2_reasoning_off.rows as Row[]).map(row => [row.arm, row]));

const NAV = [
  ['scoring', 'One problem'],
  ['conditions', 'All conditions'],
  ['problems', 'Each problem'],
  ['limits', 'Limits'],
  ['evidence', 'Records'],
  ['earlier', 'Earlier studies'],
] as const;

export default function StudyPage() {
  useEffect(() => {
    document.title = 'Zenith: does a record of missed bugs help an AI tester?';
    // The page is drawn by script, so a link to a section is honoured here.
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ''));
    if (!id) return;
    const land = () => document.getElementById(id)?.scrollIntoView({ behavior: 'instant' as ScrollBehavior });
    land();
    window.addEventListener('load', land, { once: true });
    // Web fonts change line breaks after first paint, which moves the section.
    void document.fonts?.ready.then(land);
    return () => window.removeEventListener('load', land);
  }, []);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead">
        <div className="wrap masthead__inner">
          <FamilyLockup name="Zenith" href={import.meta.env.BASE_URL} mark={<ZenithMark />} />
          <nav aria-label="Sections" className="nav">
            {NAV.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        <Hero />
        <Scoring />
        <Conditions />
        <Problems />
        <Limits />
        <Evidence />
        <Earlier />
      </main>
      <footer className="footer">
        <div className="wrap footer__inner">
          <p><a href={REPO} target="_blank" rel="noreferrer">Source repository</a></p>
          <p><a href={`${REPO}/blob/main/RESEARCH_NOTICE.md`} target="_blank" rel="noreferrer">Research notice</a></p>
        </div>
        <div className="wrap footer__family">
          <FamilySites />
        </div>
      </footer>
    </>
  );
}

function Hero() {
  return (
    <section className="study-hero wrap" id="top" aria-labelledby="title">
      <div className="study-hero__words">
        <p className="study-kicker">Zenith, current study, October 2026</p>
        <h1 id="title">Does a record of missed bugs help an AI tester on new programs?</h1>
        <p className="study-hero__lede">
          I placed a record of the faults DeepSeek V4.1 Flash missed on practice problems before each new
          task. On {study.held_out.problems} held-out Python problems, its five test inputs then exposed a
          larger share of the hidden faults. Its weights were not changed.
        </p>
        <nav className="hero__actions" aria-label="Study">
          <a className="button" href={STUDY_REPORT} target="_blank" rel="noreferrer">Read the study report</a>
          <a className="button button--ghost" href={EVIDENCE} target="_blank" rel="noreferrer">Replies and scores</a>
        </nav>
        <div className="study-films" aria-label="Videos">
          <StudyFilm id="short-zenith" label="Short video" note="The result and its limits." lead />
          <StudyFilm id="zenith" label="Full video" note="The test, the experiment and the results." />
        </div>
      </div>
      <ResultFigure />
    </section>
  );
}

/**
 * A film's still, opening YouTube in a new tab. Markup and classes follow the
 * family film slot (styles/family.css); the caption is this page's own short
 * label, since both films carry the study's long title.
 */
function StudyFilm({ id, label, note, lead = false }: { id: string; label: string; note: string; lead?: boolean }) {
  const film = FAMILY.films.find(entry => entry.id === id);
  if (!film || !isReleased(film)) return null;
  const still = `${import.meta.env.BASE_URL}${film.still}`;
  return (
    <figure className={`film-slot film-slot--small study-film${lead ? ' study-film--lead' : ''}`}>
      <a className="film-slot__frame" href={film.youtube} target="_blank" rel="noopener noreferrer"
        aria-hidden="true" tabIndex={-1}>
        <img src={`${still}-640.webp`} srcSet={`${still}-640.webp 640w, ${still}-1280.webp 1280w`}
          sizes={lead ? '(min-width: 760px) 300px, 60vw' : '(min-width: 760px) 200px, 40vw'}
          alt="" width={1280} height={720} decoding="async" />
        <span className="film-slot__play"></span>
        <span className="film-slot__time">{clock(film.duration_seconds)}</span>
      </a>
      <figcaption className="film-slot__caption">
        <p className="film-slot__title"><a href={film.youtube} target="_blank" rel="noopener noreferrer">{label}<span
          className="sr-only">: {film.title}, on YouTube, {spokenDuration(film.duration_seconds)}</span></a></p>
        <p className="film-slot__text">{note}</p>
      </figcaption>
    </figure>
  );
}

function ResultFigure() {
  return (
    <figure className="result" aria-labelledby="result-caption">
      <figcaption id="result-caption" className="result__caption">
        Share of a problem’s hidden fault classes that the tester’s five inputs exposed, mean over problems
      </figcaption>
      <dl className="result__bars">
        <div className="result__row">
          <dt>Shown nothing</dt>
          <dd><span className="result__track"><span className="result__bar" style={{ inlineSize: `${none.mean * 100}%` }}></span></span>
            <a className="result__value" href={scoreFile('cold')} target="_blank" rel="noreferrer"
              title="Saved scores for this condition">{pct(none.mean)}</a></dd>
        </div>
        <div className="result__row result__row--record">
          <dt>Shown the practice record</dt>
          <dd><span className="result__track"><span className="result__bar" style={{ inlineSize: `${record.mean * 100}%` }}></span></span>
            <a className="result__value" href={scoreFile('kept')} target="_blank" rel="noreferrer"
              title="Saved scores for this condition">{pct(record.mean)}</a></dd>
        </div>
      </dl>
      <p className="result__change">
        <strong>{points(record.diff_vs_none!)} points</strong>
        <span>95% interval {interval(record.ci95!)}</span>
      </p>
      <ul className="result__facts">
        <li>{study.held_out.problems} held-out problems with {study.held_out.fault_classes} fault classes,
          two runs of each condition.</li>
        <li>Better on {record.wins} problems, worse on {record.losses}, equal on {record.ties}. Sign
          test <var>p</var>&nbsp;=&nbsp;{record.sign_p!.toFixed(3)}.</li>
        <li>{points(record.diff_vs_none!)} is the difference of the unrounded means, {(none.mean * 100).toFixed(2)}% and {(record.mean * 100).toFixed(2)}%.</li>
        <li>About half of the gain comes from inputs that made slow faulty programs run past the time
          limit. Counting wrong values and exceptions only, by an estimate, the gain
          is {points(noTimeout.get('kept')!.diff_vs_none!)} ({interval(noTimeout.get('kept')!.ci95!)}).
          The estimate is described under <a href="#limits">Limits</a>.</li>
      </ul>
    </figure>
  );
}

function Scoring() {
  const { example } = study;
  const faultName = (id: string) => example.faults.find(fault => fault.id === id)?.models.join(', ') ?? id;
  const arms = [
    { arm: 'cold', title: 'Shown nothing' },
    { arm: 'kept', title: 'Shown the practice record' },
  ];
  return (
    <section className="study-band" id="scoring" aria-labelledby="scoring-title">
      <div className="wrap study-split">
        <div className="study-text">
          <h2 id="scoring-title">How one problem is scored</h2>
          <p>
            The tester is DeepSeek V4.1 Flash, a language model. For each problem it receives the
            specification of a short Python function (signature, docstring and examples) and returns five
            inputs. It never receives the faulty code.
          </p>
          <p>
            Each input runs on a reference solution and on every hidden faulty solution of that problem. A
            fault counts as exposed when an input gives a different return value, a different exception, or
            no answer within one second where the reference answers.
          </p>
          <p>
            The faulty solutions were written by ChatGPT, CodeGen-16B and InCoder-6B and released by the
            EvalPlus project. Each passes every original HumanEval test and fails at least one EvalPlus
            input. Solutions that fail on the same inputs count as one fault class. A fixed rule in code selects the faulty solutions; neither I nor the tester chooses them.
          </p>
          <p>
            A problem’s score is the share of its fault classes exposed. The reported score is the mean over problems, averaged over two runs.
          </p>
          <p>
            The <a href={RECORD} target="_blank" rel="noreferrer">practice record</a> covers 28 practice
            problems. For each it lists the inputs the tester chose, how many faults they exposed, and up to
            three missed faults, each with its faulty code and a candidate exposing input from the EvalPlus
            tests.
          </p>
        </div>
        <figure className="example" aria-labelledby="example-title">
          <figcaption>
            <h3 id="example-title">One held-out problem: {example.task}, <code>sort_even</code></h3>
            <p>
              The function sorts the values at the even positions of a list. Two hidden faulty versions
              exist, one written by {example.faults[0].models.join(', ')} and one
              by {example.faults[1].models.join(', ')}. These are the inputs the tester returned.
            </p>
          </figcaption>
          <div className="example__arms">
            {arms.map(({ arm, title }) => {
              const runs = example.runs.filter(run => run.arm === arm);
              const share = runs.reduce((sum, run) => sum + Object.keys(run.exposed).length, 0)
                / (runs.length * example.faults.length);
              return (
                <div className={`example__arm example__arm--${arm}`} key={arm}>
                  <h4>{title}</h4>
                  {runs.map(run => {
                    const exposedBy = new Map(Object.entries(run.exposed).map(([fault, index]) => [index as number, fault]));
                    return (
                      <div className="example__run" key={run.run}>
                        <p className="example__run-head">Run {run.run}: {Object.keys(run.exposed).length} of {example.faults.length} exposed</p>
                        <ol>
                          {run.inputs.map((input, index) => (
                            <li key={index} className={exposedBy.has(index) ? 'is-exposing' : undefined}>
                              <code>{input}</code>
                              {exposedBy.has(index) && <span className="example__hit">exposes the {faultName(exposedBy.get(index)!)} version</span>}
                            </li>
                          ))}
                        </ol>
                      </div>
                    );
                  })}
                  <p className="example__score">Score for this problem: <strong>{pct(share)}</strong></p>
                </div>
              );
            })}
          </div>
          <p className="example__note">
            The CodeGen-16B version stops on an empty list, at the line <code>assert len(l) &gt; 0</code>.
            The empty list is in neither run without the record and in both runs with it. The ChatGPT
            version was exposed in one run without the record and in neither run with it.
            Source: the saved score files
            for <a href={scoreFile('cold')} target="_blank" rel="noreferrer">nothing shown</a> and
            for <a href={scoreFile('kept')} target="_blank" rel="noreferrer">the practice record</a>.
          </p>
        </figure>
      </div>
    </section>
  );
}

/** One row's change against the tester shown nothing, on a shared scale of percentage points. */
function IntervalMark({ diff, ci, lo, hi }: { diff: number; ci: number[]; lo: number; hi: number }) {
  const at = (value: number) => `${((value * 100 - lo) / (hi - lo)) * 100}%`;
  const clear = ci[0] > 0 || ci[1] < 0;
  return (
    <span className={`ci${clear ? ' ci--clear' : ''}`} aria-hidden="true">
      <span className="ci__zero" style={{ insetInlineStart: at(0) }}></span>
      <span className="ci__bar" style={{ insetInlineStart: at(ci[0]), inlineSize: `calc(${at(ci[1])} - ${at(ci[0])})` }}></span>
      <span className="ci__dot" style={{ insetInlineStart: at(diff) }}></span>
    </span>
  );
}

function Conditions() {
  const lo = -12;
  const hi = 16;
  return (
    <section className="study-band" id="conditions" aria-labelledby="conditions-title">
      <div className="wrap">
        <div className="study-text">
          <h2 id="conditions-title">All eight conditions</h2>
          <p>
            The conditions differ only in the text placed before the specification. Change is in
            percentage points against the tester shown nothing, paired by problem, with a 95% bootstrap
            interval over problems. An interval that crosses the zero line includes no change. In the
            protocol I fixed one primary comparison, the practice record against nothing. The other
            rows are secondary or exploratory, and no <var>p</var> value is adjusted for the number of
            comparisons.
          </p>
        </div>
        <div className="conditions" role="region" aria-label="Results for all eight conditions" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">Shown to the tester</th>
                <th scope="col" className="num">Exposed</th>
                <th scope="col" className="num">Change</th>
                <th scope="col" className="conditions__plot">
                  <span className="plot-row"><span className="ci-axis" aria-hidden="true">
                    <span style={{ insetInlineStart: `${((-10 - lo) / (hi - lo)) * 100}%` }}>−10</span>
                    <span style={{ insetInlineStart: `${((0 - lo) / (hi - lo)) * 100}%` }}>0</span>
                    <span style={{ insetInlineStart: `${((10 - lo) / (hi - lo)) * 100}%` }}>+10</span>
                  </span><span className="conditions__ci">95% interval</span></span>
                </th>
                <th scope="col" className="num">Better, equal, worse</th>
                <th scope="col">Records</th>
              </tr>
            </thead>
            <tbody>
              {primary.map(row => (
                <tr key={row.arm} className={row.arm === 'kept' ? 'is-record' : undefined}>
                  <th scope="row">{ARM_LABEL[row.arm] ?? row.arm}</th>
                  <td className="num">{pct(row.mean)}</td>
                  <td className="num">{row.diff_vs_none === undefined ? '' : points(row.diff_vs_none)}</td>
                  <td className="conditions__plot">
                    {row.ci95 && row.ci95[0] * 100 >= lo
                      ? <span className="plot-row"><IntervalMark diff={row.diff_vs_none!} ci={row.ci95} lo={lo} hi={hi} />
                        <span className="conditions__ci">{interval(row.ci95)}</span></span>
                      : row.ci95
                        ? <span className="plot-row"><span className="conditions__off">left of this scale</span>
                          <span className="conditions__ci">{interval(row.ci95)}</span></span>
                        : <span className="conditions__ci conditions__ci--off">the comparison condition</span>}
                  </td>
                  <td className="num">{row.wins === undefined ? '' : `${row.wins}, ${row.ties}, ${row.losses}`}</td>
                  <td><a href={scoreFile(row.arm)} target="_blank" rel="noreferrer"
                    aria-label={`Saved scores: ${ARM_LABEL[row.arm] ?? row.arm}`}>scores</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="study-notes">
          <p>
            <strong>The rule lists.</strong> The tester wrote rules v1 from the practice record and revised
            them into v2 after its misses on 29 development problems. Neither interval excludes zero. I did not compare the record with the rule lists directly.
          </p>
          <p>
            <strong>Imagined faults.</strong> In these two conditions the tester first wrote eight faulty versions of the function and twenty candidate inputs. A program then picked five of those inputs by how many of those versions they exposed.
          </p>
          <p>
            <strong>Random inputs.</strong> Five inputs drawn at random from the EvalPlus tests, with no
            model, exposed {pct(byArm.get('random_plus')!.mean)}.
          </p>
        </div>
      </div>
    </section>
  );
}

function Problems() {
  const sorted = useMemo(
    () => [...study.problems].sort((a, b) => (a.record - a.none) - (b.record - b.none) || a.task.localeCompare(b.task, 'en', { numeric: true })),
    [],
  );
  const [selected, setSelected] = useState(() => sorted.findIndex(p => p.task === study.example.task));
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const current = sorted[selected];
  const move = (to: number) => {
    const next = Math.max(0, Math.min(sorted.length - 1, to));
    setSelected(next);
    refs.current[next]?.focus();
  };
  const diff = current.record - current.none;
  return (
    <section className="study-band" id="problems" aria-labelledby="problems-title">
      <div className="wrap">
        <div className="study-text">
          <h2 id="problems-title">The {study.held_out.problems} held-out problems, one by one</h2>
          <p>
            Each column is one problem: its score with the practice record minus its score with nothing
            shown, each averaged over two runs, in percentage points. Columns are ordered from the largest fall to the largest rise.
          </p>
        </div>
        <div className="tiles-wrap">
        <div className="tiles__axis" aria-hidden="true">
          <span style={{ insetBlockStart: 0 }}>+100</span>
          <span style={{ insetBlockStart: 'calc(var(--up) * 0.5)' }}>+50</span>
          <span style={{ insetBlockStart: 'var(--up)' }}>0</span>
          <span style={{ insetBlockStart: 'calc(var(--up) * 1.5)' }}>−50</span>
        </div>
        <div className="tiles" role="group"  aria-label="Change in score for each held-out problem"
          onKeyDown={event => {
            if (event.key === 'ArrowRight') { event.preventDefault(); move(selected + 1); }
            if (event.key === 'ArrowLeft') { event.preventDefault(); move(selected - 1); }
            if (event.key === 'Home') { event.preventDefault(); move(0); }
            if (event.key === 'End') { event.preventDefault(); move(sorted.length - 1); }
          }}>
          {sorted.map((problem, index) => {
            const change = problem.record - problem.none;
            const kind = change > 1e-9 ? 'better' : change < -1e-9 ? 'worse' : 'equal';
            return (
              <button type="button" key={problem.task} ref={el => { refs.current[index] = el; }}
                className={`tile tile--${kind}`} aria-pressed={index === selected}
                tabIndex={index === selected ? 0 : -1}
                aria-label={`${problem.task}: ${pct(problem.none)} with nothing shown, ${pct(problem.record)} with the record`}
                onClick={() => setSelected(index)} onMouseEnter={() => setSelected(index)}>
                <span className="tile__bar" style={{ blockSize: kind === 'equal' ? undefined : `calc(var(--up) * ${Math.abs(change).toFixed(4)})` }}></span>
              </button>
            );
                    })}
        </div>
        </div>
        <ul className="tiles__key">
          <li className="tiles__key--better">Better with the record: {record.wins}</li>
          <li className="tiles__key--equal">Equal: {record.ties}</li>
          <li className="tiles__key--worse">Worse: {record.losses}</li>
        </ul>
        <p className="tiles__readout" aria-live="polite">
          <strong>{current.task}</strong>, {current.faults} fault {current.faults === 1 ? 'class' : 'classes'}:{' '}
          {pct(current.none)} with nothing shown, {pct(current.record)} with the practice record
          {Math.abs(diff) > 1e-9 ? ` (${points(diff)} points)` : ' (no change)'}.
        </p>
        <p className="study-small">
          Left and right arrow keys move between problems. The inputs and exposed faults for every problem
          and run are in the score files
          for <a href={scoreFile('cold')} target="_blank" rel="noreferrer">nothing shown</a> and <a
            href={scoreFile('kept')} target="_blank" rel="noreferrer">the practice record</a>.
        </p>
      </div>
    </section>
  );
}

function Limits() {
  const noneClean = noTimeout.get('cold')!;
  const recordClean = noTimeout.get('kept')!;
  const valid = record.all_inputs_valid_subset!;
  const lo = -4;
  const hi = 16;
  const rows = [
    { label: 'All exposures, timeouts included', detail: `${pct(none.mean)} to ${pct(record.mean)}`, diff: record.diff_vs_none!, ci: record.ci95! },
    { label: 'Wrong values and exceptions only', detail: `${pct(noneClean.mean)} to ${pct(recordClean.mean)}`, diff: recordClean.diff_vs_none!, ci: recordClean.ci95! },
    { label: `The ${valid.problems} problems with five valid inputs in both conditions and both runs`, detail: 'all exposures', diff: valid.diff_vs_none, ci: valid.ci95 },
  ];
  return (
    <section className="study-band study-band--tint" id="limits" aria-labelledby="limits-title">
      <div className="wrap study-split study-split--even">
        <div>
          <div className="study-text">
            <h2 id="limits-title">What the gain is made of</h2>
            <p>
              Very large inputs made slow faulty programs run past the one-second limit, which counts as exposed. About half of the gain involves such timeouts. That share comes from
              classifying each exposed fault by its first saved exposing input, so it is an estimate. The second and third rows are exploratory.
            </p>
          </div>
          <table className="gain">
            <thead>
              <tr><th scope="col">Counted</th><th scope="col" className="num">Gain</th>
                <th scope="col" className="gain__plot"><span className="plot-row"><span className="ci-axis" aria-hidden="true">
                  <span style={{ insetInlineStart: `${((0 - lo) / (hi - lo)) * 100}%` }}>0</span>
                  <span style={{ insetInlineStart: `${((10 - lo) / (hi - lo)) * 100}%` }}>+10</span>
                </span><span className="conditions__ci">95% interval</span></span></th></tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.label}>
                  <th scope="row">{row.label}<span className="gain__detail">{row.detail}</span></th>
                  <td className="num">{points(row.diff)}</td>
                  <td className="gain__plot"><span className="plot-row"><IntervalMark diff={row.diff} ci={row.ci} lo={lo} hi={hi} />
                    <span className="conditions__ci">{interval(row.ci)}</span></span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="study-small">
            Counting wrong values and exceptions only, the record was better on {recordClean.wins} problems
            and worse on {recordClean.losses}. Figures from <a href={RESULTS} target="_blank" rel="noreferrer">results.json</a>.
          </p>
        </div>
        <div className="study-text">
          <h2 className="study-h2--side">Limits</h2>
          <ul className="limits">
            <li>One tester model, with fixed weights, on one benchmark of short Python functions.</li>
            <li>With reasoning switched off, no condition helped. The tester shown nothing scored {pct(reasoningOff.get('cold_nr')!.mean)},
              shown the practice record {pct(reasoningOff.get('kept_nr')!.mean)}, and shown the rule
              lists {pct(reasoningOff.get('lessons_v1_nr')!.mean)} and {pct(reasoningOff.get('lessons_v2_nr')!.mean)}.
              I added this second experiment after the main conditions were scored, and it reused the held-out problems.</li>
            <li>The faults come from three code models released in 2022 and 2023.</li>
            <li>EvalPlus inputs define which solutions are faulty, so a fault that no EvalPlus input exposes
              is not counted. Problems are weighted equally.</li>
            <li>In the protocol I wrote that different return values and exceptions would count. The frozen scoring code also counted timeouts. Both versions are in the table in this section.</li>
            <li>In the protocol I wrote, before the held-out run, that a positive result would be evidence of transfer within this benchmark, under a five-input budget, for one model, and no evidence about large systems, other languages or other models.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function Evidence() {
  return (
    <section className="study-band" id="evidence" aria-labelledby="evidence-title">
      <div className="wrap study-split study-split--even">
        <div className="study-text">
          <h2 id="evidence-title">The plan and when it was fixed</h2>
          <ol className="timeline">
            <li>
              <time dateTime="2026-10-19">19 October 2026</time>
              <p>I committed the <a href={PROTOCOL} target="_blank" rel="noreferrer">protocol</a> before
                any held-out call (commit <code>9b6c2b3</code>). It contains the split of problems, the
                conditions, the prompts and the analysis, with a hash of each frozen input.</p>
            </li>
            <li>
              <time dateTime="2026-10-19">19 October 2026, addendum A</time>
              <p>I added a second experiment, with reasoning switched off, after the main conditions were scored.</p>
            </li>
            <li>
              <time dateTime="2026-10-19">19 October 2026, addendum B</time>
              <p>One scoring job stalled on very large inputs. Each job was then capped at 120 seconds and
                stalled jobs were rerun in isolation, where a fault that cannot finish within 20 seconds counts
                as exposed. The rule was applied to every condition and no model call or reply changed.</p>
            </li>
          </ol>
        </div>
        <div className="study-text">
          <h2 className="study-h2--side">Saved records</h2>
          <ul className="records">
            <li><a href={STUDY_REPORT} target="_blank" rel="noreferrer">Study report</a>: method, results and limits.</li>
            <li><a href={RESULTS} target="_blank" rel="noreferrer">results.json</a>: the figures in the tables on this page.</li>
            <li><a href={EVIDENCE} target="_blank" rel="noreferrer">Replies, ledger and scores</a>: every
              reply with its reasoning, the cost ledger, the fault population and the held-out score files.</li>
            <li>Cost: 1,565 model calls for $5.70.</li>
          </ul>
          <p>
            One command re-scores the saved replies with no model calls. It needs HumanEvalPlus v0.1.10 and runs code written by the three code models, so it is meant for a disposable environment.
          </p>
          <div className="replay">
            <pre><code>{REPLAY}</code></pre>
            <CopyButton text={REPLAY} label="Copy command" />
          </div>
          <p className="study-small">
            The study’s files are at revision <code>{study.revision.slice(0, 7)}</code>, on the branch
            of <a href={`${REPO}/pull/13`} target="_blank" rel="noreferrer">pull request 13</a>.
          </p>
        </div>
      </div>
    </section>
  );
}

function Earlier() {
  return (
    <section className="study-band study-earlier" id="earlier" aria-labelledby="earlier-title">
      <div className="wrap">
        <div className="study-text">
          <h2 id="earlier-title">Earlier studies</h2>
          <p>
            Before this study I ran three separate experiments in Zenith: on program repair, on
            model-written testers for SQLite clients, and on a learning algorithm that predicts a
            program’s later behaviour from its earlier actions. I reported them in a short paper dated
            21 October 2026. In the repair experiment, correct answers on later inputs rose from 259 of
            576 to 365 of 576. That figure is from those experiments.
          </p>
          <p className="study-earlier__links">
            <a href={EARLIER_HREF}>Read the earlier paper on this site</a>
            <a href={`${import.meta.env.BASE_URL}assets/paper.pdf`} target="_blank" rel="noreferrer">Earlier paper (PDF)</a>
            <a href={`${REPO}/blob/main/docs/status.md`} target="_blank" rel="noreferrer">Results and replay links for the earlier studies</a>
          </p>
        </div>
      </div>
    </section>
  );
}
