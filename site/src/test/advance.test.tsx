import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { clearApiCache } from '../api';
import { PaperAside } from '../components/PaperAside';
import type { Chapter, Paper } from '../api';

const current = '/api/v1/evidence/advance-campaign';
const historical = '/api/v1/evidence/observation-learning-result';
const source = { path: 'docs/advance-campaign-20261014.json', sha256: 'fixture', url: 'https://example.org/current.json' };

function receipt() {
  return { schema: 'zenith_advance_campaign_v1', status: 'complete',
    summary: 'Controlled campaign fixture: analysis includes stopped construction.',
    total_calls: 13, total_reported_cost_usd: '0.0243',
    accounting_boundary: 'One reserved attempt has an unknown charge; reported cost is partial.',
    conformance_studies: [
      { id: 'fixture-stopped', complete: false, calls: 10, reported_cost_usd: '0.0213',
        model: 'fixture-model-a', reasoning_effort: 'low', panel_summary: null },
      { id: 'fixture-complete', complete: true, calls: 3, reported_cost_usd: '0.0030',
        model: 'fixture-model-b', reasoning_effort: 'none', panel_summary: { correct: 1, total: 2 } },
    ], memory: { summary: 'Authored continuation-memory fixture; model acquisition is separate.' } };
}

function mockSite(data: unknown, { published = true, status = 200 } = {}) {
  const chapters = ['lab', 'oracle', 'evolve', 'results'].map(id => ({
    id, title: id, evidence_kind: id === 'results' ? 'measured_execution' : 'authored_mechanism',
    graph_url: null, figure_url: null, paper_section: null, available: true,
    document_url: id === 'results' ? '/api/v1/documents/advance-synthesis' : null,
    // A stale chapter binding must never override the explicit active ID.
    evidence_urls: id === 'results' ? [historical] : [],
  }));
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    let code = 200;
    if (url.endsWith('/site')) body = { title: 'Zenith', chapters, documents: {}, figures: {},
      active_evidence_id: 'advance-campaign', evidence: {
        ...(published ? { 'advance-campaign': current } : {}),
        'observation-learning-result': historical,
        'decomposition-result': '/api/v1/evidence/decomposition-result',
      }, data_note: 'Current evidence retains separate scopes.', notice: 'Fixture', capabilities: {} };
    else if (url === current) { body = { source, data }; code = status; }
    else if (url.endsWith('/documents/paper')) body = { content: '', source };
    else if (url.endsWith('/documents/advance-synthesis')) body = {
      id: 'advance-synthesis', format: 'markdown', content: '# Current synthesis\n\nBounded evidence.',
      source: { ...source, path: 'docs/advance-returns-20261014.md' },
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
afterEach(() => cleanup());

it('uses the current receipt, separate study statuses and retained historical links', async () => {
  mockSite(receipt());
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Campaign analysis complete' })).toBeInTheDocument();
  expect(screen.getByRole('rowheader', { name: /fixture-stopped/ })).toBeInTheDocument();
  expect(screen.getByText('Incomplete')).toBeInTheDocument();
  expect(screen.getByText('Complete')).toBeInTheDocument();
  expect(screen.getByText(/13 recorded call attempts; \$0.0243 reported cost/)).toBeInTheDocument();
  expect(screen.getByText(/One reserved attempt has an unknown charge/)).toBeInTheDocument();
  expect(screen.getByText(/Authored continuation-memory fixture/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Historical: Native observation-learning study/ })).toHaveAttribute('href', historical);
  expect(screen.queryByRole('heading', { name: 'Protected evaluation complete' })).toBeNull();
  expect(screen.queryByText('1/2')).toBeNull();
  expect(screen.getAllByRole('link', { name: 'Previous edition (PDF)' })).toHaveLength(2);
  expect(screen.queryByRole('link', { name: 'Read the paper (PDF)' })).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => !String(url).includes('/graph') && String(url) !== historical)).toBe(true);
  const toggle = screen.getByText('Read the repository’s own explanation').parentElement as HTMLDetailsElement;
  toggle.open = true;
  fireEvent(toggle, new Event('toggle'));
  expect(await screen.findByRole('heading', { name: 'Current synthesis' })).toBeInTheDocument();
});

it('shows pending current evidence when only historical receipts exist', async () => {
  mockSite(receipt(), { published: false });
  render(<App />);
  expect(await screen.findByText('Current campaign results pending.')).toBeInTheDocument();
  expect(screen.getByText(/No current receipt is published/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Historical: Native observation-learning study/ })).toHaveAttribute('href', historical);
  expect(screen.queryByText(/Initial native comparison/)).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => String(url) !== historical)).toBe(true);
});

it('shows a current receipt fetch error without substituting historical results', async () => {
  mockSite(receipt(), { status: 503 });
  render(<App />);
  expect(await screen.findByText('Current-campaign receipt unavailable.')).toBeInTheDocument();
  expect(screen.getByText(/The current-campaign receipt is unavailable:/)).toBeInTheDocument();
  expect(screen.queryByText('fixture-stopped')).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => String(url) !== historical)).toBe(true);
});

it.each([
  { ...receipt(), schema: 'zenith_observation_learning_evidence_v1' },
  { ...receipt(), conformance_studies: null },
])('withholds unsupported current receipts despite older schema availability', async data => {
  mockSite(data);
  render(<App />);
  expect(await screen.findByText('Current-campaign receipt schema unsupported.')).toBeInTheDocument();
  expect(screen.getByText(/The current-campaign receipt has an unsupported schema/)).toBeInTheDocument();
  expect(screen.queryByText(/Initial native comparison/)).toBeNull();
  expect(screen.queryByText('fixture-stopped')).toBeNull();
});

it('labels the retained PDF separately from the current source and its line numbers', () => {
  const section = { id: 'results', start_line: 40, end_line: 50, source,
    source_url: 'https://example.org/current.tex#L40', pdf_url: '/assets/paper.pdf#nameddest=results', citation_ids: [] };
  const chapter = { id: 'results', title: 'Results', evidence_urls: [], paper_section: section } as unknown as Chapter;
  const paper = { source, citations: [], sections: [section], pdf_current: false } as unknown as Paper;
  render(<PaperAside chapter={chapter} paper={paper} latex={null} />);
  expect(screen.getByRole('link', { name: 'Previous edition PDF' })).toHaveAttribute('href', '/assets/paper.pdf#nameddest=results');
  expect(screen.getByRole('link', { name: 'Measured comparisons' })).toHaveAttribute('href', 'https://example.org/current.tex#L40');
  expect(screen.getByText(/current LaTeX source, lines 40/)).toBeInTheDocument();
});
