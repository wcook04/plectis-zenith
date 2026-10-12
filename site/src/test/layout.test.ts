import { describe, expect, it } from 'vitest';
import type { Graph } from '../api';
import { layoutGraph, neighbourhood } from '../components/graph/layout';
import { aggregateState, normalizeState } from '../lib/status';
import { latexToText, sectionTitle, shortCitation } from '../lib/latex';
import { figureUrl } from '../components/Markdown';
import { nearestVariant, parseVariants } from '../components/Research';
import fixture from './fixtures/lab-topology.json';

const lab = fixture as unknown as Graph;

describe('graph layout', () => {
  it('collapses lane-parallel siblings into a readable two-pass overview', () => {
    const layout = layoutGraph(lab, new Set());
    const ids = layout.items.map((i) => i.id);
    expect(ids).toContain('group:feeds');
    expect(ids).toContain('group:miners');
    expect(ids).toContain('group:miners_v2');
    expect(layout.items).toHaveLength(10);
    expect(layout.bands.map((b) => b.title)).toEqual(['First pass', 'Second pass']);
    // Every native node is represented exactly once.
    expect(new Set(layout.renderIdOf.keys())).toEqual(new Set(lab.nodes.map((n) => n.id)));
  });

  it('never overlaps two cards', () => {
    for (const expanded of [new Set<string>(), new Set(['feeds', 'miners', 'miners_v2'])]) {
      const { items } = layoutGraph(lab, expanded);
      for (let i = 0; i < items.length; i++) {
        for (let j = i + 1; j < items.length; j++) {
          const a = items[i];
          const b = items[j];
          const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
          expect(overlap, `${a.id} overlaps ${b.id}`).toBe(false);
        }
      }
    }
  });

  it('routes skip and cross-band edges and marks implied skips as redundant', () => {
    const { edges } = layoutGraph(lab, new Set());
    const decideToDirected = edges.find((e) => e.source === 'lab_decide' && e.target === 'group:miners_v2');
    expect(decideToDirected?.routed).toBe(true);
    const feedsToSynthesis2 = edges.find((e) => e.source === 'group:feeds' && e.target === 'group:miners_v2');
    expect(feedsToSynthesis2?.skip).toBe(true);
    // Feeds reach the directed miners through the first pass too, so the
    // direct skip edge is implied and hidden in the overview.
    expect(feedsToSynthesis2?.redundant).toBe(true);
    expect(edges.some((e) => !e.redundant && e.source === 'lab_seed_state')).toBe(true);
  });

  it('expands a family into its native members', () => {
    const layout = layoutGraph(lab, new Set(['miners']));
    const miners = layout.items.filter((i) => i.kind === 'node' && i.id.startsWith('lab_miner_') && !i.id.includes('v2'));
    expect(miners).toHaveLength(7);
    expect(layout.frames.map((f) => f.id)).toContain('frame:miners');
  });

  it('computes lineage from authored edges', () => {
    const n = neighbourhood(lab, 'lab_cross_corr_v1');
    expect([...n.inputs].every((id) => id.startsWith('lab_miner_'))).toBe(true);
    expect(n.consumers.has('lab_orient')).toBe(true);
    expect(n.ancestors.has('global_stock_feed')).toBe(true);
    expect(n.descendants.has('lab_integrity')).toBe(true);
  });
});

describe('run states', () => {
  it('keeps reused evidence distinct from a fresh execution', () => {
    expect(normalizeState('loaded')).toBe('loaded');
    expect(normalizeState('success')).toBe('success');
    expect(normalizeState('not_reached')).toBe('not_reached');
    expect(aggregateState(['loaded', 'loaded'])).toBe('loaded');
    expect(aggregateState(['loaded', 'failure'])).toBe('failure');
  });
});

describe('paper and figure helpers', () => {
  it('labels margin citations by author and year', () => {
    expect(shortCitation('D. Silver et al. Mastering the game of Go without human knowledge. \\emph{Nature} 550:354--359, 2017.')).toBe('Silver et al. 2017');
    expect(shortCitation('Zenith. \\href{https://x}{Original-feed window experiment}, 12 October 2026.')).toBe('Zenith 2026: Original-feed window experiment');
  });

  it('reads section titles from the manuscript', () => {
    const tex = ['\\hypertarget{lab}{}', '\\textbf{2. The executable graph and failure diagnosis.}', 'text', '\\hypertarget{oracle}{}', 'figure'].join('\n');
    expect(sectionTitle(tex, 1, 3)).toBe('Section 2, The executable graph and failure diagnosis');
    expect(sectionTitle(tex, 4, 5)).toBe('Section 2, The executable graph and failure diagnosis');
  });

  it('maps repository figures to the backend asset routes', () => {
    const figures = { lab: '/assets/graphs/lab.svg' };
    expect(figureUrl('https://github.com/wcook04/plectis-zenith/blob/main/docs/graphs/lab.svg', figures)).toBe('/assets/graphs/lab.svg');
    expect(figureUrl('https://example.org/x.png', figures)).toBe('https://example.org/x.png');
  });
});

describe('text helpers', () => {
  it('turns bibliography LaTeX into text', () => {
    expect(
      latexToText('A. Karpathy. \\emph{autoresearch}. Source at \\href{https://x}{\\texttt{228791fb499a}} (code).'),
    ).toBe('A. Karpathy. autoresearch. Source at 228791fb499a (code).');
    expect(latexToText("``Gradient Descent'' and 354--359")).toBe('\u201cGradient Descent\u201d and 354\u2013359');
  });

  it('reads the prompt-setting catalogue and renders the nearest written variant', () => {
    const md = [
      '| Setting | Small variation |',
      '|---|---|',
      '| `0.0` | Neutral. |',
      '| `0.1` | Mild caution. |',
      '| `0.2` | More weight. |',
      '| `1.0` | Strongest emphasis. |',
    ].join('\n');
    const variants = parseVariants(md);
    expect(variants.map((v) => v.setting)).toEqual([0, 0.1, 0.2, 1]);
    expect(nearestVariant(variants, 0.15).setting).toBe(0.1); // tie goes to the lower setting
    expect(nearestVariant(variants, 0.7).setting).toBe(1);
  });
});
