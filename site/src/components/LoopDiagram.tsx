// The proposed evaluation loop (paper Figure 1) as an explorable diagram.
// One reading direction, left to right; the cutoff is the vertical boundary.
// Solid arrows are the per-round flow; dashed arrows are the separate
// comparison, which has not run end to end and is drawn as a proposal.
import { useState } from 'react';
import { LOOP_STAGES } from '../content/copy';
import { useMediaQuery } from '../lib/hooks';

type StageId = (typeof LOOP_STAGES)[number]['id'];

const W = 168;
const H = 66;
const BOX: Record<StageId, { x: number; y: number; w?: number }> = {
  feeds: { x: 22, y: 92 },
  lab: { x: 214, y: 92 },
  frozen: { x: 406, y: 92 },
  later: { x: 646, y: 92 },
  oracle: { x: 838, y: 92 },
  evolve: { x: 1030, y: 92 },
  compare: { x: 646, y: 262, w: 552 },
};
const CUTOFF_X = 612;
const VIEW_W = 1220;

export function LoopDiagram() {
  const narrow = useMediaQuery('(max-width: 760px)');
  const [active, setActive] = useState<StageId>('lab');
  const stage = LOOP_STAGES.find((s) => s.id === active)!;

  const details = (
    <div className="loop-detail" aria-live="polite">
      <h3 className="loop-detail__title">{stage.title}</h3>
      <dl>
        <dt>Receives</dt>
        <dd>{stage.receives}</dd>
        <dt>Produces</dt>
        <dd>{stage.produces}</dd>
      </dl>
    </div>
  );

  if (narrow) {
    return (
      <figure className="loop loop--list">
        <ol className="loop-list">
          {LOOP_STAGES.map((s, index) => (
            <li key={s.id} className={`loop-list__item side-${s.side}`}>
              {s.side === 'after' && LOOP_STAGES[index - 1].side !== 'after' && (
                <p className="loop-list__cutoff">Cutoff: everything below comes later</p>
              )}
              <button type="button" aria-pressed={active === s.id} onClick={() => setActive(s.id)}>
                <strong>{s.title}</strong>
                <span>{s.detail}</span>
              </button>
              {active === s.id && details}
            </li>
          ))}
        </ol>
        <figcaption>
          The proposed loop. The comparison on another window is a separate test, and the full loop has not yet run end to end.
        </figcaption>
      </figure>
    );
  }

  const box = (id: StageId) => ({ ...BOX[id], w: BOX[id].w ?? W });
  const right = (id: StageId) => box(id).x + box(id).w;
  const midY = (id: StageId) => box(id).y + H / 2;

  return (
    <figure className="loop">
      <svg
        viewBox={`0 0 ${VIEW_W} 352`}
        className="loop-svg"
        role="group"
        aria-labelledby="loop-title loop-desc"
      >
        <title id="loop-title">The proposed Zenith evaluation loop</title>
        <desc id="loop-desc">
          Saved feeds before the cutoff go to the Lab, which freezes a prediction. After the cutoff, later evidence
          and the frozen prediction go to Oracle, which diagnoses a failure; Evolve proposes one change. A separate
          comparison runs the original and revised graphs on another window.
        </desc>
        <defs>
          <marker id="loop-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="var(--edge-strong)" />
          </marker>
        </defs>

        <rect x="8" y="34" width={CUTOFF_X - 16} height="304" className="loop-zone loop-zone--before" />
        <rect x={CUTOFF_X + 8} y="34" width={VIEW_W - 8 - CUTOFF_X - 8} height="304" className="loop-zone loop-zone--after" />
        <text x="22" y="58" className="loop-zone__label">Before the cutoff: all the Lab may see</text>
        <text x={CUTOFF_X + 22} y="58" className="loop-zone__label">After the cutoff</text>
        <line x1={CUTOFF_X} y1="20" x2={CUTOFF_X} y2="346" className="loop-cutoff" />
        <text x={CUTOFF_X} y="14" textAnchor="middle" className="loop-cutoff__label">Cutoff t</text>

        {/* Per-round flow */}
        <path d={`M${right('feeds')} ${midY('feeds')}H${box('lab').x}`} className="loop-wire" markerEnd="url(#loop-arrow)" />
        <path d={`M${right('lab')} ${midY('lab')}H${box('frozen').x}`} className="loop-wire" markerEnd="url(#loop-arrow)" />
        <path d={`M${right('later')} ${midY('later')}H${box('oracle').x}`} className="loop-wire" markerEnd="url(#loop-arrow)" />
        <path d={`M${right('oracle')} ${midY('oracle')}H${box('evolve').x}`} className="loop-wire" markerEnd="url(#loop-arrow)" />
        <path
          d={`M${box('frozen').x + W / 2} ${box('frozen').y}V74H${box('oracle').x + W / 2}V${box('oracle').y}`}
          className="loop-wire"
          markerEnd="url(#loop-arrow)"
        />
        <text x={(CUTOFF_X + box('oracle').x + W / 2) / 2 + 30} y="68" textAnchor="middle" className="loop-wire__label">
          frozen record
        </text>

        {/* Separate comparison: dashed, a proposal */}
        <path
          d={`M${box('evolve').x + W / 2} ${box('evolve').y + H}V${box('compare').y}`}
          className="loop-wire loop-wire--test"
          markerEnd="url(#loop-arrow)"
        />
        <text x={box('evolve').x + W / 2 + 10} y={box('compare').y - 40} className="loop-wire__label">revision</text>
        <path
          d={`M${box('lab').x + W / 2} ${box('lab').y + H}V${midY('compare')}H${box('compare').x}`}
          className="loop-wire loop-wire--test"
          markerEnd="url(#loop-arrow)"
        />
        <text x={box('lab').x + W / 2 + 10} y={midY('compare') - 8} className="loop-wire__label">original graph</text>

        {LOOP_STAGES.map((s) => {
          const b = box(s.id);
          const isActive = s.id === active;
          return (
            <g
              key={s.id}
              className={`loop-node side-${s.side}${isActive ? ' is-active' : ''}`}
              role="button"
              tabIndex={0}
              aria-pressed={isActive}
              aria-label={`${s.title}: ${s.detail}`}
              onClick={() => setActive(s.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setActive(s.id);
                }
              }}
            >
              <rect x={b.x} y={b.y} width={b.w} height={H} rx={s.side === 'boundary' ? 2 : 8} className="loop-node__box" />
              <text x={b.x + 14} y={b.y + 28} className="loop-node__title">{s.title}</text>
              <text x={b.x + 14} y={b.y + 48} className="loop-node__detail">{s.detail}</text>
            </g>
          );
        })}
      </svg>
      <div className="loop__foot">
      {details}
      <figcaption>
        Proposed loop, after the paper’s Figure 1. Square corners mark a saved record. Dashed arrows are a separate
        comparison that has not yet run end to end; a diagnosis or revision is not shown to be correct until it does.
        Select a stage to see what it receives and produces.
      </figcaption>
      </div>
    </figure>
  );
}
