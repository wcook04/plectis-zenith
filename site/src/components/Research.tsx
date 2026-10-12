// The proposed context-conditioned prompt mechanism (paper Section 3, Figure 4)
// and a hands-on illustration of one prompt setting. The variants are read
// from docs/research-direction.md at runtime. Nothing here runs a model or
// represents a trained controller.
import { useId, useMemo, useState } from 'react';
import type { Doc } from '../api';
import { useMediaQuery } from '../lib/hooks';

export type Variant = { setting: number; text: string };

export function parseVariants(markdown: string): Variant[] {
  const rows: Variant[] = [];
  markdown.split('\n').forEach((line) => {
    const match = /^\|\s*`?(\d(?:\.\d+)?)`?\s*\|\s*(.+?)\s*\|\s*$/.exec(line.trim());
    if (match) rows.push({ setting: Number(match[1]), text: match[2] });
  });
  return rows.sort((a, b) => a.setting - b.setting);
}

// Nearest written variant, ties to the lower setting (the fixed tie-break the
// research direction calls for).
export function nearestVariant(variants: Variant[], value: number): Variant {
  return variants.reduce((best, v) => {
    const d = Math.abs(v.setting - value);
    const bd = Math.abs(best.setting - value);
    return d < bd - 1e-9 ? v : best;
  }, variants[0]);
}

export function SettingsIllustration({ doc }: { doc: Doc }) {
  const variants = useMemo(() => parseVariants(doc.content), [doc]);
  const [value, setValue] = useState(0.1);
  const id = useId();
  if (variants.length < 2) return null;
  const chosen = nearestVariant(variants, value);
  return (
    <figure className="settings">
      <p className="settings__badge">Illustration. No controller has been implemented; the slider selects among written examples and runs no model.</p>
      <div className="settings__grid">
        <div className="settings__control">
          <label htmlFor={id} className="settings__label">
            Caution about sentiment-driven consensus, for the Polymarket miner
          </label>
          <input
            id={id}
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value}
            onChange={(event) => setValue(Number(event.target.value))}
            aria-valuetext={`${value.toFixed(2)}, renders the ${chosen.setting.toFixed(1)} wording`}
          />
          <div className="settings__ticks" aria-hidden="true">
            {variants.map((v) => (
              <span key={v.setting} style={{ left: `${v.setting * 100}%` }}>
                {v.setting.toFixed(1)}
              </span>
            ))}
          </div>
          <p className="settings__value">
            Setting <strong>{value.toFixed(2)}</strong> renders the written variant for{' '}
            <strong>{chosen.setting.toFixed(1)}</strong>.
            {Math.abs(chosen.setting - value) > 1e-9 && ' Values between variants render the nearest one; text is never blended.'}
          </p>
        </div>
        <div className="settings__prompt">
          <p className="settings__fixed">
            <span className="settings__tag">Fixed at every setting</span>
            Same inputs (seed state and the Polymarket feed), same probability filters, ranking by absolute
            probability change, deduplication and output structure.
          </p>
          <p className="settings__variant" aria-live="polite">
            <span className="settings__tag">Interpretation guidance at {chosen.setting.toFixed(1)}</span>
            {chosen.text}
          </p>
        </div>
      </div>
      <figcaption>
        Example wording from{' '}
        <a href={doc.source.url} target="_blank" rel="noreferrer">
          the research direction
        </a>
        . The numbers are hand-picked indices into a written catalogue, not learned values, and a larger setting need
        not perform better.
      </figcaption>
    </figure>
  );
}

const MECH = [
  { id: 'context', x: 20, title: 'Available context', lines: ['VIX, sentiment and other', 'features at the cutoff'] },
  { id: 'controller', x: 200, title: 'Prompt controller', lines: ['Shared encoder and a', 'small head per node'] },
  { id: 'settings', x: 380, title: 'Settings for one node', lines: ['One number per', 'component: 0.1, 0.2 …'] },
  { id: 'assemble', x: 560, title: 'Assemble the prompt', lines: ['Fixed task + chosen', 'variants; save exact text'] },
  { id: 'task', x: 740, title: 'Same reasoning task', lines: ['Base model weights', 'stay fixed'] },
  { id: 'output', x: 920, title: 'Saved output', lines: ['Passed to the next', 'nodes in the graph'] },
];

export function MechanismDiagram() {
  const narrow = useMediaQuery('(max-width: 760px)');
  if (narrow) {
    return (
      <figure className="mech mech--list">
        <p className="settings__badge">Proposed. Not implemented or tested.</p>
        <ol className="mech-list">
          {MECH.map((m) => (
            <li key={m.id}>
              <strong>{m.title}</strong> {m.lines.join(' ')}
            </li>
          ))}
        </ol>
        <p className="mech-list__dev">
          Development only: fit or select the controller on development cases from context, configurations and
          observed losses, freeze it, then test on later cases.
        </p>
      </figure>
    );
  }
  const W = 160;
  const H = 70;
  const Y = 150;
  return (
    <figure className="mech">
      <p className="settings__badge">Proposed. Not implemented or tested.</p>
      <svg viewBox="0 0 1100 400" className="mech-svg" role="img" aria-labelledby="mech-title mech-desc">
        <title id="mech-title">Proposed context-conditioned prompt selection</title>
        <desc id="mech-desc">
          Context available at the cutoff goes to a shared controller, which outputs settings for one node. The
          settings select written variants that are assembled with the fixed task into a prompt. The same reasoning
          task runs with the base model fixed and saves its output. A separate development loop fits the controller
          from observed losses and freezes it before testing.
        </desc>
        <defs>
          <marker id="mech-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="var(--edge-strong)" />
          </marker>
        </defs>
        <text x="20" y="28" className="loop-zone__label">At prediction time, for each reasoning node</text>

        <rect x="560" y="44" width={W} height="58" className="mech-fixed" />
        <text x="574" y="68" className="loop-node__title">Fixed task</text>
        <text x="574" y="88" className="loop-node__detail">Job, evidence rules, output</text>
        <path d={`M${560 + W / 2} 102V${Y}`} className="loop-wire" markerEnd="url(#mech-arrow)" />

        <rect x="740" y="44" width={W} height="58" className="mech-fixed" />
        <text x="754" y="68" className="loop-node__title">Permitted inputs</text>
        <text x="754" y="88" className="loop-node__detail">Its feed + earlier outputs</text>
        <path d={`M${740 + W / 2} 102V${Y}`} className="loop-wire" markerEnd="url(#mech-arrow)" />

        {MECH.slice(0, -1).map((m) => (
          <path key={`w-${m.id}`} d={`M${m.x + W} ${Y + H / 2}H${m.x + 180}`} className="loop-wire" markerEnd="url(#mech-arrow)" />
        ))}
        {MECH.map((m) => (
          <g key={m.id} className={`mech-node mech-node--${m.id}`}>
            <rect x={m.x} y={Y} width={W} height={H} rx={m.id === 'output' || m.id === 'settings' ? 2 : 8} className="loop-node__box" />
            <text x={m.x + 14} y={Y + 24} className="loop-node__title">{m.title}</text>
            {m.lines.map((line, i) => (
              <text key={line} x={m.x + 14} y={Y + 43 + i * 15} className="loop-node__detail">{line}</text>
            ))}
          </g>
        ))}

        <rect x="12" y="262" width="1076" height="128" className="loop-zone loop-zone--dev" />
        <text x="26" y="286" className="loop-zone__label">Development only, never on test cases</text>
        {[
          { x: 200, t: 'Context, settings', d: 'and observed losses' },
          { x: 470, t: 'Fit or select the controller', d: 'on development cases' },
          { x: 740, t: 'Freeze the controller', d: 'then test on later cases' },
        ].map((b, i, all) => (
          <g key={b.t}>
            <rect x={b.x} y="304" width="230" height="62" rx="8" className="loop-node__box mech-dev" />
            <text x={b.x + 14} y="330" className="loop-node__title">{b.t}</text>
            <text x={b.x + 14} y="350" className="loop-node__detail">{b.d}</text>
            {i < all.length - 1 && (
              <path d={`M${b.x + 230} 335H${all[i + 1].x}`} className="loop-wire loop-wire--test" markerEnd="url(#mech-arrow)" />
            )}
          </g>
        ))}
        <path d={`M${580} 304V${Y + H + 28}H${280}V${Y + H}`} className="loop-wire loop-wire--test" markerEnd="url(#mech-arrow)" />
        <text x="296" y={Y + H + 22} className="loop-wire__label">trains the controller only</text>
      </svg>
      <figcaption>
        After the paper’s Figure 4. Settings select text; they do not scale evidence or the model’s reasoning.
        Backpropagation could train the controller, but no gradient passes through the language model or the text
        choice, and later test outcomes stay out of development.
      </figcaption>
    </figure>
  );
}
