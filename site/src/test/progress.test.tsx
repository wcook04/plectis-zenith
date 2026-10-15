import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { clearApiCache } from '../api';
import { PaperAside } from '../components/PaperAside';
import type { Chapter, Paper } from '../api';

const current = '/api/v1/evidence/progress-campaign';
const advance = '/api/v1/evidence/advance-campaign';
const historical = '/api/v1/evidence/observation-learning-result';
const client = '/api/v1/evidence/client-investigation';
const source = { path: 'docs/studies/native/progress-campaign-20261014.json', sha256: 'fixture', url: 'https://example.org/current.json' };

function receipt() {
  return { schema: 'zenith_progress_campaign_report_v1', status: 'complete',
    summary: 'Controlled qualification passed; diagnostic scores remain separate.',
    claim_boundary: 'Three authored native contracts; no transfer claim.',
    source_bindings: { 'examples/conformance/qualification/manifest.json': 'fixture-hash' },
    conformance_studies: [
      { id: 'fixture-v4-qualification', version: 'v4', stage: 'qualification', complete: true, parent_episodes: 3,
        actual_calls: 10, reported_cost_usd: '0.0200', unknown_cost_calls: 0,
        model: 'fixture-model-a', reasoning_effort: 'low', qualification: { passed: true },
        forfeited: true, forfeiture_reason: 'Repair candidates were blocked by admission.' },
      { id: 'fixture-qualification', version: 'v5', stage: 'qualification', complete: true, parent_episodes: 3,
        actual_calls: 10, reported_cost_usd: '0.0213', unknown_cost_calls: 1,
        model: 'fixture-model-a', reasoning_effort: 'low', qualification: { passed: true } },
      { id: 'fixture-diagnostic', version: 'v5', stage: 'diagnostic', complete: true, parent_episodes: 12,
        actual_calls: 33, reported_cost_usd: '0.0830', unknown_cost_calls: 0,
        model: 'fixture-model-b', reasoning_effort: 'none',
        panel_summary: { confirmation: { overall: {
          parent: { correct: 3, total: 12, errors: 0 },
          fixed: { correct: 8, total: 12, errors: 0 },
          direct_masked: { correct: 6, total: 12, errors: 0 },
          direct_adaptive: { correct: 7, total: 12, errors: 0 },
        } } } },
    ], learner: { native_configurations: 8, authored_native_families: 4,
      conditions: { ordinary_witness: { acquisition_source_calls: 11395 },
        generic_singletons: { acquisition_source_calls: 11379 } },
      ordinary_minus_generic_acquisition_source_calls: 16,
      boundary: 'No acquired-question gain over generic singleton questions.' } };
}

function clientReceipt() {
  return { schema: 'zenith_client_investigation_report_v1', complete: true,
    protected_panel_opened: true, target_count: 5, total_failing_targets: 4,
    model_attempts: 42, reported_model_cost_usd: '0.005186696', unknown_cost_attempts: 0,
    model: 'fixture-client-model', reasoning_effort: 'none',
    boundary: 'Authored SQLite within-family feasibility; no independent transfer claim.',
    artifacts: { procedure: { error: null }, ordinary_reuse: { error: null } },
    arm_metrics: Object.fromEntries([
      ['procedure', 0, 0], ['ordinary_reuse', 0, 0], ['same_history', 4, 20],
      ['cold', 3, 18], ['fixed', 4, 15],
    ].map(([arm, found, probes]) => [arm, { failed_targets_detected: found,
      total_failing_targets: 4, query_slots: probes, valid_probes: probes, model_call_attempts: 0,
      runs: 5, not_run_targets: 0 }])),
  };
}

function mockSite(data: unknown, { published = true, status = 200, clientData = undefined,
  clientStatus = 200, clientVersions = {} }: { published?: boolean; status?: number;
    clientData?: unknown; clientStatus?: number; clientVersions?: Record<string, unknown> } = {}) {
  const clients: Record<string, unknown> = { ...(clientData === undefined ? {} : { 'client-investigation': clientData }), ...clientVersions };
  const chapters = ['idea', 'lab', 'oracle', 'evolve', 'results', 'next'].map(id => ({
    id, title: id, evidence_kind: id === 'results' ? 'measured_execution' : 'authored_mechanism',
    graph_url: null, figure_url: null, paper_section: null, available: true,
    document_url: id === 'results' ? '/api/v1/documents/progress-synthesis' : null,
    // A stale chapter binding must never override the explicit active ID.
    evidence_urls: id === 'results' ? [historical] : [],
  }));
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    let code = 200;
    if (url.endsWith('/site')) body = { title: 'Zenith', chapters,
      documents: Object.fromEntries(['client-investigation-protocol', 'client-investigation-protocol-v2',
        ...Object.keys(clients)].map(id => [id, `/api/v1/documents/${id}`])), figures: {},
      active_evidence_id: 'progress-campaign', evidence: {
        ...(published ? { 'progress-campaign': current } : {}),
        ...Object.fromEntries(Object.keys(clients).map(id => [id, `/api/v1/evidence/${id}`])),
        'advance-campaign': advance,
        'observation-learning-result': historical,
        'decomposition-result': '/api/v1/evidence/decomposition-result',
      }, data_note: 'Current evidence retains separate scopes.', notice: 'Fixture', capabilities: {} };
    else if (url === current) { body = { source, data }; code = status; }
    else if (url.startsWith(client)) { body = { source: { ...source, path: `${url.slice('/api/v1/evidence/'.length)}.json`, url: 'https://example.org/client.json' }, data: clients[url.slice('/api/v1/evidence/'.length)] }; code = clientStatus; }
    else if (url.endsWith('/documents/paper')) body = { content: '', source };
    else if (url.endsWith('/documents/progress-synthesis')) body = {
      id: 'progress-synthesis', format: 'markdown', content: '# Current synthesis\n\nBounded evidence.',
      source: { ...source, path: 'docs/history/progress-returns-20261014.md' },
      base_url: 'https://example.org/docs/', headings: [] };
    else if (url.endsWith('/paper')) body = { source, citations: [], sections: [], pdf_sha256: 'fixture' };
    else throw new Error(`Unexpected request: ${url}`);
    return new Response(JSON.stringify(body), { status: code, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
}

beforeEach(() => {
  clearApiCache();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('max-width'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); });

it('uses the current receipt, separate study scores and retained historical links', async () => {
  mockSite(receipt());
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Repairing database, cache and text programs' })).toBeInTheDocument();
  for (const label of ['How the model interface was tested, costs and full results', 'Separate learner comparison', 'Earlier experiment records', 'Earlier studies, graphs and paper edition']) {
    fireEvent.click(screen.getByText(label));
  }
  expect(screen.getByRole('rowheader', { name: /fixture-qualification/ })).toBeInTheDocument();
  expect(screen.getByRole('rowheader', { name: /fixture-v4-qualification/ })).toBeInTheDocument();
  expect(screen.getByRole('rowheader', { name: /fixture-diagnostic/ })).toBeInTheDocument();
  expect(screen.getByText(/Interface passed/)).toBeInTheDocument();
  expect(screen.getAllByText(/Repair comparison not completed/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Repair candidates were blocked by admission/)).toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Current status' })).toBeNull();
  expect(within(screen.getByRole('navigation', { name: 'Chapters' })).getAllByRole('link').map(link => link.textContent))
    .toEqual(['The research question', 'How it works', 'What we found', 'What we still need to test', 'Paper']);
  expect(document.getElementById('lab')).not.toBeNull();
  expect(document.getElementById('evolve')).not.toBeNull();
  expect(screen.getByText(/1 unknown-charge attempts/)).toBeInTheDocument();
  expect(screen.getByText('7/12')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Repairing the learner’s memory' })).toBeInTheDocument();
  expect(screen.getByText('11395')).toBeInTheDocument();
  expect(screen.getByText('11379')).toBeInTheDocument();
  expect(screen.getByText(/Passing these examples shows agreement on those particular inputs/)).toBeInTheDocument();
  expect(screen.getByText(/Passing that preliminary test does not establish that its repairs work/)).toBeInTheDocument();
  expect(screen.getByText(/These are software executions, not requests to an AI/)).toBeInTheDocument();
  expect(screen.getByText(/Three authored native contracts; no transfer claim/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Historical: Earlier Advance repair/ })).toHaveAttribute('href', advance);
  expect(screen.getByRole('link', { name: /Historical: Earlier experiment learning to predict software responses/ })).toHaveAttribute('href', historical);
  expect(screen.queryByRole('heading', { name: 'Protected evaluation complete' })).toBeNull();
  expect(screen.queryByText('13 recorded call attempts')).toBeNull();
  expect(screen.getAllByRole('link', { name: 'Previous edition (PDF)' })).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Current paper source' })).toHaveAttribute('href', source.url);
  expect(screen.getByRole('link', { name: 'Current LaTeX source on GitHub' })).toHaveAttribute('href', source.url);
  expect(screen.queryByRole('link', { name: 'Read the paper (PDF)' })).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => !String(url).includes('/graph') && String(url) !== historical)).toBe(true);
  const toggle = screen.getByText('Read the detailed method and research notes').parentElement as HTMLDetailsElement;
  toggle.open = true;
  fireEvent(toggle, new Event('toggle'));
  expect(await screen.findByRole('heading', { name: 'Current synthesis' })).toBeInTheDocument();
});

it('shows pending current evidence when only historical receipts exist', async () => {
  mockSite(receipt(), { published: false });
  render(<App />);
  expect(await screen.findByText('Current Progress campaign results pending.')).toBeInTheDocument();
  expect(screen.getByText(/No current result file is published/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Historical: Earlier experiment learning to predict software responses/ })).toHaveAttribute('href', historical);
  expect(screen.queryByText(/Initial native comparison/)).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => String(url) !== historical)).toBe(true);
});

it('shows a current receipt fetch error without substituting historical results', async () => {
  mockSite(receipt(), { status: 503 });
  render(<App />);
  expect(await screen.findByText('The current experiment result file could not be loaded.')).toBeInTheDocument();
  expect(screen.getByText(/The current experiment result file could not be loaded:/)).toBeInTheDocument();
  expect(screen.queryByText('fixture-qualification')).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => String(url) !== historical)).toBe(true);
});

it.each([
  { ...receipt(), schema: 'zenith_advance_campaign_v1' },
  { ...receipt(), conformance_studies: null },
])('withholds unsupported current receipts despite older schema availability', async data => {
  mockSite(data);
  render(<App />);
  expect(await screen.findByText('The current experiment result file uses an unsupported format.')).toBeInTheDocument();
  expect(screen.getByText('The current experiment result file uses an unsupported format; no outcomes are displayed.')).toBeInTheDocument();
  expect(screen.queryByText(/Initial native comparison/)).toBeNull();
  expect(screen.queryByText('fixture-qualification')).toBeNull();
});

it('keeps outdated PDF links out of current paper section citations', () => {
  const section = { id: 'results', start_line: 40, end_line: 50, source,
    source_url: 'https://example.org/current.tex#L40', pdf_url: '/assets/paper.pdf#nameddest=results', citation_ids: [] };
  const chapter = { id: 'results', title: 'Results', evidence_urls: [], paper_section: section } as unknown as Chapter;
  const paper = { source, citations: [], sections: [section], pdf_current: false } as unknown as Paper;
  render(<PaperAside chapter={chapter} paper={paper} latex={null} />);
  expect(screen.queryByRole('link', { name: 'Previous edition PDF' })).toBeNull();
  expect(screen.getByRole('link', { name: 'Measured comparisons' })).toHaveAttribute('href', 'https://example.org/current.tex#L40');
  expect(screen.getByText(/paper text and formatting code, lines 40/)).toBeInTheDocument();
});

it('publishes the client pilot independently while the native campaign is pending', async () => {
  mockSite(receipt(), { published: false, clientData: clientReceipt() });
  render(<App />);
  const heading = await screen.findByRole('heading', { name: 'Reusable tests' });
  const pilot = within(heading.parentElement as HTMLElement);
  expect(await pilot.findByText(/42 recorded model attempts; \$0.005186696 reported inference cost/)).toBeInTheDocument();
  expect(pilot.getByText(/5 later database programs were tested; 4 contained a known fault/)).toBeInTheDocument();
  expect(pilot.getByText(/Neither saved tester tried an input on the later programs/)).toBeInTheDocument();
  const frozen = pilot.getByRole('rowheader', { name: 'Saved learned tester' }).parentElement as HTMLElement;
  expect(within(frozen).getByText('0/4')).toBeInTheDocument();
  const fresh = pilot.getByRole('rowheader', { name: 'New AI, earlier results' }).parentElement as HTMLElement;
  expect(within(fresh).getByText('4/4')).toBeInTheDocument();
  expect(pilot.getByText(/how often the tester would report a fault incorrectly/)).toBeInTheDocument();
  expect(pilot.getByRole('link', { name: 'Read the saved tester-reuse results and costs' })).toHaveAttribute('href', 'https://example.org/client.json');
  expect(pilot.getByRole('link', { name: 'Read the client-pilot protocol' })).toHaveAttribute('href', '/api/v1/documents/client-investigation-protocol');
  expect(screen.getByText('Current Progress campaign results pending.')).toBeInTheDocument();
});

it.each([
  ['diagnostic_pending', 'comparison in progress'],
  ['qualification_failed', 'preliminary interface test failed'],
  ['protocol_deviation', 'the experiment departed from its written procedure'],
])('translates campaign status %s into reader-facing text', async (status, label) => {
  mockSite({ ...receipt(), status });
  render(<App />);
  expect(await screen.findByText(`Current repair experiments: ${label}; 3 studies published.`)).toBeInTheDocument();
  expect(screen.queryByText(new RegExp(status))).toBeNull();
});

it('shows the latest client version while retaining both earlier engineering failures', async () => {
  const first = clientReceipt();
  const invalid = { ...clientReceipt(), artifacts: { procedure: { error: 'SyntaxError: fixture' }, ordinary_reuse: { error: null } },
    arm_metrics: { ...first.arm_metrics, procedure: { ...first.arm_metrics.procedure, runs: 0, not_run_targets: 5 } } };
  const latest = { ...clientReceipt(), reasoning_effort: 'low', model_attempts: 40,
    reported_model_cost_usd: '0.012345678',
    arm_metrics: { ...first.arm_metrics,
      procedure: { ...first.arm_metrics.procedure, failed_targets_detected: 3, query_slots: 10, valid_probes: 8 },
      ordinary_reuse: { ...first.arm_metrics.ordinary_reuse, failed_targets_detected: 3, query_slots: 10, valid_probes: 9 },
      same_history: { ...first.arm_metrics.same_history, failed_targets_detected: 3, model_call_attempts: 15 },
    } };
  mockSite(receipt(), { clientData: first, clientVersions: {
    'client-investigation-v2': invalid, 'client-investigation-v2-low': latest,
  } });
  render(<App />);
  const pilot = within((await screen.findByRole('heading', { name: 'Reusable tests' })).parentElement as HTMLElement);
  const history = pilot.queryByText('Earlier client attempts');
  if (history) fireEvent.click(history);
  expect(await pilot.findByText(/40 recorded model attempts; \$0.012345678 reported inference cost/)).toBeInTheDocument();
  expect(pilot.getByText(/Latest published version: v2, reasoning low/)).toBeInTheDocument();
  const investigator = pilot.getByRole('rowheader', { name: 'Saved learned tester' }).parentElement as HTMLElement;
  expect(within(investigator).getByText('3/4')).toBeInTheDocument();
  const fresh = pilot.getByRole('rowheader', { name: 'New AI, earlier results' }).parentElement as HTMLElement;
  expect(within(fresh).getByText('15')).toBeInTheDocument();
  expect(pilot.getByText(/matched the ordinary reusable tester/)).toBeInTheDocument();
  expect(pilot.getByText(/Both saved testers stopped without trying any inputs/)).toBeInTheDocument();
  expect(pilot.getByText(/The generated tester could not run; 5 later programs not tested/)).toBeInTheDocument();
  expect(pilot.getAllByRole('link', { name: /^Result data$/ }).map(link => link.getAttribute('href'))).toEqual([
    client, `${client}-v2`, `${client}-v2-low`,
  ]);
  expect(pilot.getAllByRole('link', { name: /^Analysis$/ })).toHaveLength(3);
  expect(pilot.getByRole('link', { name: 'Read the client-pilot protocol' })).toHaveAttribute('href', '/api/v1/documents/client-investigation-protocol-v2');
});

it('labels a skipped invalid client investigator as not run instead of a measured zero', async () => {
  const first = clientReceipt();
  const invalid = { ...first, artifacts: { ...first.artifacts, procedure: { error: 'SyntaxError: fixture' } },
    arm_metrics: { ...first.arm_metrics, procedure: { ...first.arm_metrics.procedure, runs: 0, not_run_targets: 5 } } };
  mockSite(receipt(), { clientData: first, clientVersions: { 'client-investigation-v2': invalid } });
  render(<App />);
  const pilot = within((await screen.findByRole('heading', { name: 'Reusable tests' })).parentElement as HTMLElement);
  const history = pilot.queryByText('Earlier client attempts');
  if (history) fireEvent.click(history);
  const header = await pilot.findByRole('rowheader', { name: 'Saved learned tester' });
  const row = within(header.parentElement as HTMLElement);
  expect(row.getByText(/Not run/)).toBeInTheDocument();
  expect(row.queryByText('0/4')).toBeNull();
  expect(pilot.getByText(/program error: SyntaxError: fixture/)).toBeInTheDocument();
});

it('does not display protected client outcomes for an incomplete pilot', async () => {
  mockSite(receipt(), { clientData: { ...clientReceipt(), complete: false, protected_panel_opened: false } });
  render(<App />);
  expect(await screen.findByText(/Results on the later programs appear only after the tester/)).toBeInTheDocument();
  expect(screen.queryByRole('rowheader', { name: 'Saved learned tester' })).toBeNull();
  expect(screen.getByRole('heading', { name: 'Repairing database, cache and text programs' })).toBeInTheDocument();
});

it('loads one static API snapshot under a deployment prefix and preserves public read links', async () => {
  vi.stubEnv('VITE_ZENITH_SNAPSHOT', '1');
  vi.stubEnv('VITE_ZENITH_API', '/plectis-zenith');
  vi.resetModules();
  const transport = await import('../api');
  const site = { active_evidence_id: 'progress-campaign' };
  const paper = { title: 'Snapshot paper' };
  const graph = { node_count: 3 };
  globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({
    schema: 'zenith_public_api_snapshot_v1', routes: {
      '/api/v1/site': site, '/api/v1/paper': paper, '/api/v1/graph?mission=lab': graph,
    },
  }), { headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
  expect(await Promise.all([transport.api.site(), transport.api.paper(), transport.api.graph('/api/v1/graph?mission=lab')]))
    .toEqual([site, paper, graph]);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith('/plectis-zenith/public-api.json', expect.anything());
  expect(transport.apiUrl('/api/v1/documents/paper')).toBe('/plectis-zenith/api/v1/documents/paper.json');
  expect(transport.apiUrl('/assets/paper.pdf')).toBe('/plectis-zenith/assets/paper.pdf');
  expect(transport.apiUrl('https://example.org/source')).toBe('https://example.org/source');
  await expect(transport.api.evidence('/api/v1/evidence/private-run')).rejects.toMatchObject({
    status: 404, code: 'unknown_snapshot_route',
  });
  expect(fetch).toHaveBeenCalledTimes(1);
  transport.clearApiCache();
});

it('rejects an unsupported static snapshot without trying live endpoints', async () => {
  vi.stubEnv('VITE_ZENITH_SNAPSHOT', '1');
  vi.resetModules();
  const transport = await import('../api');
  globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ schema: 'unknown', routes: {} }))) as typeof fetch;
  await expect(transport.api.site()).rejects.toMatchObject({ status: 502, code: 'snapshot_schema' });
  expect(fetch).toHaveBeenCalledTimes(1);
  transport.clearApiCache();
});

it.each([
  { clientData: { ...clientReceipt(), arm_metrics: null }, message: /tester-reuse result file uses an unsupported format/ },
  { clientData: { ...clientReceipt(), reported_model_cost_usd: '-1' }, message: /tester-reuse result file uses an unsupported format/ },
  { clientData: clientReceipt(), clientStatus: 503, message: /tester-reuse result file could not be loaded/ },
])('withholds unavailable or unsupported client results without affecting the native receipt', async ({ message, ...options }) => {
  mockSite(receipt(), options);
  render(<App />);
  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(screen.queryByRole('rowheader', { name: 'Saved learned tester' })).toBeNull();
  expect(screen.getByRole('heading', { name: 'Repairing database, cache and text programs' })).toBeInTheDocument();
});
