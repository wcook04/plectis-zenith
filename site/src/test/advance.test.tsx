import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { clearApiCache } from '../api';

const advance = '/api/v1/evidence/advance-campaign';
const historical = '/api/v1/evidence/observation-learning-result';
const source = { path: 'docs/history/advance-campaign-20261014.json', sha256: 'fixture', url: 'https://example.org/advance.json' };

beforeEach(() => {
  clearApiCache();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('max-width'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});
afterEach(() => cleanup());

it('still renders an Advance receipt when older site metadata names it active', async () => {
  const chapters = ['lab', 'oracle', 'evolve', 'results'].map(id => ({
    id, title: id, evidence_kind: id === 'results' ? 'measured_execution' : 'authored_mechanism',
    graph_url: null, figure_url: null, paper_section: null, available: true,
    document_url: id === 'results' ? '/api/v1/documents/advance-synthesis' : null,
    evidence_urls: id === 'results' ? [advance] : [],
  }));
  const receipt = { schema: 'zenith_advance_campaign_v1', status: 'complete',
    summary: 'Advance fixture keeps stopped construction separate.',
    total_calls: 13, total_reported_cost_usd: '0.0243',
    accounting_boundary: 'One reserved attempt has an unknown charge.',
    conformance_studies: [{ id: 'fixture-stopped', complete: false, calls: 10,
      reported_cost_usd: '0.0213', model: 'fixture-model', reasoning_effort: 'low' }],
    memory: { summary: 'Separate authored continuation-memory fixture.' } };
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.endsWith('/site')) body = { title: 'Zenith', chapters, documents: {}, figures: {},
      active_evidence_id: 'advance-campaign', evidence: {
        'advance-campaign': advance, 'observation-learning-result': historical,
      }, data_note: 'Advance evidence retains its own scope.', notice: 'Fixture', capabilities: {} };
    else if (url === advance) body = { source, data: receipt };
    else if (url.endsWith('/documents/paper')) body = { content: '', source };
    else if (url.endsWith('/documents/advance-synthesis')) body = {
      id: 'advance-synthesis', format: 'markdown', content: '# Earlier synthesis', source,
      base_url: 'https://example.org/docs/', headings: [] };
    else if (url.endsWith('/paper')) body = { source, citations: [], sections: [], pdf_sha256: 'fixture' };
    else throw new Error(`Unexpected request: ${url}`);
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;

  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Advance campaign analysis complete' })).toBeInTheDocument();
  expect(screen.getByRole('rowheader', { name: /fixture-stopped/ })).toBeInTheDocument();
  expect(screen.getByText('Incomplete')).toBeInTheDocument();
  expect(screen.getByText(/13 recorded call attempts; \$0.0243 reported cost/)).toBeInTheDocument();
  expect(screen.getByText(/Separate authored continuation-memory fixture/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Historical: Native observation-learning study/ })).toHaveAttribute('href', historical);
  expect(screen.queryByRole('link', { name: /Historical: Advance conformance campaign/ })).toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([url]) => String(url) !== historical)).toBe(true);
});
