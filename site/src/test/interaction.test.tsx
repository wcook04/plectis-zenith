// Interaction tests run the phone layout (the staged list), which renders the
// same nodes and inspector without a canvas, so jsdom can exercise them.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Graph, RunSummary } from '../api';
import { clearApiCache } from '../api';
import { GraphExplorer } from '../components/graph/GraphExplorer';
import { Markdown } from '../components/Markdown';
import fixture from './fixtures/lab-topology.json';

const lab = fixture as unknown as Graph;

function mockMatchMedia(narrow: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('max-width') ? narrow : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

type Responder = (url: string) => { status?: number; body: unknown; delay?: number };

function mockFetch(responder: Responder) {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const { status = 200, body, delay = 0 } = responder(url);
    if (delay) await new Promise((r) => setTimeout(r, delay));
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
}

const nodeBody = (id: string) => lab.nodes.find((n) => n.id === id);

beforeEach(() => {
  clearApiCache();
  mockMatchMedia(true);
});
afterEach(() => cleanup());

describe('node inspector', () => {
  it('opens a node, shows its current instruction and walks to an upstream input', async () => {
    mockFetch((url) => ({ body: nodeBody(decodeURIComponent(url.split('/nodes/')[1])) }));
    render(<GraphExplorer graph={lab} title="Lab" />);
    fireEvent.click(screen.getAllByRole('button', { name: /Synthesis 1/ })[0]);
    const dialog = await screen.findByRole('dialog', { name: /Synthesis 1/ });
    expect(within(dialog).getByText('Current instruction')).toBeInTheDocument();
    expect(within(dialog).getByText('Instruction for lab_cross_corr_v1')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Copy instruction' })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: /Measurements miner/ }));
    await screen.findByRole('dialog', { name: /Measurements miner/ });
    fireEvent.keyDown(screen.getByRole('heading', { name: 'Measurements miner' }), { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('shows a failed run record and never leaves another run’s evidence visible', async () => {
    const summary = (run_id: string, outcome: string): RunSummary => ({
      run_id,
      mission: 'lab',
      source_kind: 'native_run',
      subject_run: null,
      grade: 'red',
      grade_reason: '',
      timestamp: 0,
      node_outcomes: { lab_cross_corr_v1: outcome },
    });
    mockFetch((url) => {
      if (url.includes('/runs/RUN_A/')) {
        return {
          body: {
            run_id: 'RUN_A',
            node_id: 'lab_cross_corr_v1',
            status: 'failure',
            source_kind: 'native_run',
            subject_run: null,
            artifact: { status: 'failure', metadata: { error: 'output ran out' }, data: { attempt_log: [], last_invalid_output: '{"swarms": [' } },
            artifact_bytes: 10,
            artifact_omitted: false,
            artifact_error: null,
            attempts: [
              { attempt: 1, status: 'failure', error_class: 'JSON_PARSE_ERROR', errors: ['Unterminated string'], prompt_snippet: '[TRUNCATED len=900]\n…', prompt_length: 900, prompt_truncated: false, output_text: '{"swarms": [', output_length: 12, output_truncated: false },
            ],
          },
        };
      }
      if (url.includes('/runs/RUN_B/')) {
        return {
          delay: 30,
          body: {
            run_id: 'RUN_B', node_id: 'lab_cross_corr_v1', status: 'not_started', source_kind: 'native_run', subject_run: null,
            artifact: null, artifact_bytes: null, artifact_omitted: false, artifact_error: 'missing', attempts: [],
          },
        };
      }
      return { body: nodeBody('lab_cross_corr_v1') };
    });

    const { rerender } = render(
      <GraphExplorer graph={lab} title="Lab" initialSelected="lab_cross_corr_v1" run={{ kind: 'local', runId: 'RUN_A', summary: summary('RUN_A', 'failure') }} />,
    );
    expect(await screen.findByText('output ran out')).toBeInTheDocument();
    expect(screen.getByText('Unterminated string')).toBeInTheDocument();
    expect(screen.getByText(/excerpt only/)).toBeInTheDocument();

    await act(async () => {
      rerender(
        <GraphExplorer graph={lab} title="Lab" initialSelected="lab_cross_corr_v1" run={{ kind: 'local', runId: 'RUN_B', summary: summary('RUN_B', 'not_started') }} />,
      );
    });
    // While RUN_B loads, RUN_A's failure must already be gone.
    expect(screen.queryByText('output ran out')).toBeNull();
    expect(await screen.findByText(/this means no output, not a success/)).toBeInTheDocument();
  });

  it('keeps loaded evidence labelled as loaded', async () => {
    mockFetch(() => ({ body: nodeBody('lab_miner_measurements') }));
    render(
      <GraphExplorer
        graph={lab}
        title="Lab"
        run={{ kind: 'receipt', label: 'Receipt', sourceUrl: '/x', states: { lab_miner_measurements: 'loaded', lab_decide: 'failure' }, calls: {}, note: '' }}
      />,
    );
    const measurements = screen.getAllByRole('button', { name: /Measurements miner/ })[0];
    expect(measurements).toHaveAccessibleName(/Loaded/);
    expect(screen.getAllByRole('button', { name: /Decide \(CP1\)/ })[0]).toHaveAccessibleName(/Failed/);
  });
});

describe('markdown from the backend', () => {
  it('drops raw HTML and unsafe links and resolves relative links', () => {
    const { container } = render(
      <Markdown
        base="https://github.com/wcook04/plectis-zenith/blob/main/docs/"
        source={'<script>alert(1)</script>\n\n[bad](javascript:alert(1)) [doc](graphs.md)'}
      />,
    );
    expect(container.querySelector('script')).toBeNull();
    const links = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(links).not.toContain('javascript:alert(1)');
    expect(links).toContain('https://github.com/wcook04/plectis-zenith/blob/main/docs/graphs.md');
  });
});

describe('synthetic observed-system edition', () => {
  it('reads the preparation receipt and marks Seed as a prepared request, nothing as ran', async () => {
    mockFetch(() => ({ body: nodeBody('lab_seed_state') }));
    const { Preparation } = await import('../components/Preparation');
    const result = {
      id: 'demo-result',
      source: { path: 'examples/demo/result.json', sha256: 'x', url: 'u' },
      data: {
        schema: 'zenith_demo_preparation_result_v1',
        completed_count: lab.nodes.filter((n) => n.group === 'feeds').length,
        pending_nodes: ['lab_seed_state'],
        model_calls: 0,
        forecast_complete: false,
        claim_boundary: 'Preparation only.',
      },
    };
    render(<Preparation result={result} sources={null} labGraph={lab} localRuns={false} />);
    expect(screen.getByText(/The record claims only that the inputs were loaded/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Seed state/ })[0]).toHaveAccessibleName(/Request prepared/);
    expect(screen.getAllByRole('button', { name: /Measurements feed/ })[0]).toHaveAccessibleName(/Loaded/);
    expect(screen.queryAllByRole('button', { name: /, Ran\./ })).toHaveLength(0);
  });

  it('renders column-and-row payloads as a table', async () => {
    const { JsonView } = await import('../components/JsonView');
    render(<JsonView label="Synthetic" value={{ columns: ['target_id', 'value'], rows: [['signal_a', 0.1]] }} />);
    expect(screen.getByRole('columnheader', { name: 'target_id' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'signal_a' })).toBeInTheDocument();
  });
});

describe('dependency disclosure', () => {
  it('lists a node’s direct original-feed input even though the overview hides that edge', async () => {
    mockFetch((url) => ({ body: nodeBody(decodeURIComponent(url.split('/nodes/')[1])) }));
    render(<GraphExplorer graph={lab} title="Lab" />);
    fireEvent.click(screen.getAllByRole('button', { name: /Measurements directed miner/ })[0]);
    const dialog = await screen.findByRole('dialog', { name: /Measurements directed miner/ });
    const reads = within(dialog).getByRole('heading', { name: 'Reads' }).parentElement!;
    expect(within(reads).getByRole('button', { name: /Measurements feed/ })).toBeInTheDocument();
  });
});
