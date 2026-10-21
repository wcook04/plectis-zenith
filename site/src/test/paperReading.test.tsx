import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { Markdown } from '../components/Markdown';
import { clearApiCache, type Paper, type PaperReading, type Site } from '../api';

const source = { path: 'paper/zenith.tex', sha256: 'paper-fixture', url: 'https://example.org/zenith.tex' };
const figure = '/assets/repair-loop.svg';

function reading(): PaperReading {
  return {
    abstract: 'Manuscript abstract: a bounded comparison of retained tests.',
    disclosure: '**Authorship and AI use.** The manuscript records the role of AI and limits of human review.',
    sections: [
      { id: 'idea', title: '1. Programs and observations', blocks: [
        { kind: 'markdown', content: '**Observation tables.** The paper defines its measured state [1](#ref-weighted).' },
        { kind: 'figure', url: figure, alt: 'The loop typeset in the manuscript', caption: 'The same paper figure and its source caption.' },
      ] },
      { id: 'results', title: '2. Experiments and limitations', blocks: [
        { kind: 'markdown', content: '**Measured comparison.** This result comes from the manuscript payload.\n\n| Method | Faults |\n| --- | --- |\n| Manuscript control | 4 / 4 |\n| Manuscript tester | 3 / 4 |' },
      ] },
      { id: 'next', title: '3. Research directions', blocks: [
        { kind: 'markdown', content: 'The manuscript proposes a frozen-improver comparison. [Plectis mathematical corpus](https://github.com/wcook04/plectis-erdos)' },
      ] },
    ],
  };
}

function mockPaper(payload = reading(), active = 'progress-campaign') {
  const site: Site = {
    schema: 'fixture', title: 'Metadata title must not replace the manuscript',
    paper_url: '/api/v1/paper', active_evidence_id: active,
    chapters: ['idea', 'lab', 'oracle', 'evolve', 'results', 'next'].map(id => ({
      id, title: `Old independent ${id} heading`, evidence_kind: 'authored_mechanism',
      available: true, document_url: null, figure_url: null, graph_url: null,
      paper_section: null, evidence_urls: [],
    })),
    notice: 'Experimental manuscript fixture.', notice_url: '/api/v1/documents/notice',
    documents: { paper: '/api/v1/documents/paper', results: '/api/v1/documents/results', 'continuation-learner': '/api/v1/documents/continuation-learner' },
    figures: { 'paper-loop': figure },
    evidence: { 'progress-campaign': '/api/v1/evidence/progress-campaign', 'continuation-learner': '/api/v1/evidence/continuation-learner' },
    local_runs_enabled: false, capabilities: {},
  };
  const paper: Paper = {
    title: 'Zenith: the actual manuscript title', source, source_url: "/api/v1/documents/paper",
    pdf_url: '/assets/paper.pdf', pdf_sha256: 'paper-pdf-fixture', pdf_current: true,
    sections: [], notice_url: site.notice_url, reading: payload,
    references_source: { path: 'paper/references.json', sha256: 'references-fixture', url: 'https://example.org/references.json' },
    citations: [{ id: 'weighted', latex: 'J. Worrell. Exactly Learning Weighted Automata over a Field.',
      urls: ['https://example.org/weighted.pdf'], used_at: [{ line: 12, locator: 'Proposition 1' }],
      review: { reviewed_source: { edition: 'Undated Oxford notes', sha256: 'source-fixture' },
        application: 'The paired rank-growth invariant.',
        source_locators: [{ id: 'rank', locator: 'Proposition 1, pp. 2–3',
          supports: 'Retain the access history and distinguishing test.', boundary: 'Requires a full-rank observation table.' }] } }],
  };
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.endsWith('/site')) body = site;
    else if (url === '/api/v1/paper') body = paper;
    else if (url.endsWith('/documents/continuation-learner')) body = {
      format: 'markdown', content: 'Reproduce the saved continuation learner.',
      base_url: 'https://example.org/learner.md', source,
    };
    else if (url.endsWith('/documents/paper')) body = {
      content: '\\\\[4pt]\nWill Cook \\quad\\textbullet\\quad 15 October 2026\n', source,
    };
    else throw new Error(`The paper reading view must not request independent narrative or results: ${url}`);
    return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
}

beforeEach(() => {
  clearApiCache();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('max-width'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});
afterEach(() => cleanup());

it('reads the title, abstract, sections and navigation from the manuscript payload', async () => {
  mockPaper();
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Zenith: the actual manuscript title' })).toBeInTheDocument();
  // The document title is set in an effect after the heading renders.
  await waitFor(() => expect(document.title).toBe('Zenith: the actual manuscript title'));
  expect(screen.getByText('Manuscript abstract: a bounded comparison of retained tests.')).toBeInTheDocument();
  expect(screen.getByText('Authorship and AI use.')).toBeInTheDocument();
  expect(screen.getByText(/The manuscript records the role of AI and limits of human review/)).toBeInTheDocument();
  expect(screen.getByText(/The manuscript proposes a frozen-improver comparison/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Plectis mathematical corpus' })).toHaveAttribute('href', 'https://github.com/wcook04/plectis-erdos');
  const nav = within(screen.getByRole('navigation', { name: 'Chapters' })).getAllByRole('link');
  expect(nav.map(link => link.getAttribute('href'))).toEqual(['#idea', '#results', '#next', '#paper']);
  expect(nav.map(link => link.textContent)).toEqual([
    '1. Programs and observations', '2. Experiments and limitations', '3. Research directions', 'Paper',
  ]);
  for (const id of ['idea', 'results', 'next']) expect(document.getElementById(id)).not.toBeNull();
  expect(screen.queryByText(/Old independent/)).toBeNull();
  expect(screen.queryByText(/An AI can suggest a repair to a faulty program/)).toBeNull();
  expect(screen.queryByText(/The longer-term question is whether experience improves/)).toBeNull();
  expect(screen.queryByRole('heading', { name: 'Repairing database, cache and text programs' })).toBeNull();
  expect(screen.queryByRole('region', { name: 'Current status' })).toBeNull();
  expect(screen.getByRole('link', { name: 'Current paper source' })).toHaveAttribute('href', source.url);
  expect(screen.getAllByRole('link', { name: 'Read the paper (PDF)' }).every(link => link.getAttribute('href') === '/assets/paper.pdf')).toBe(true);
  expect(screen.getByRole('link', { name: 'Results and replay links' })).toHaveAttribute('href', '/api/v1/documents/results');
  expect(vi.mocked(fetch).mock.calls.every(([url]) => !String(url).includes('/evidence/') && !String(url).includes('/graph'))).toBe(true);
});

it('renders the paper table, citation targets, reviewed references and the exact figure asset', async () => {
  mockPaper();
  render(<App />);
  expect(await screen.findByRole('cell', { name: 'Manuscript control' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: '4 / 4' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '1' })).toHaveAttribute('href', '#ref-weighted');
  expect(document.getElementById('ref-weighted')).toHaveTextContent('Exactly Learning Weighted Automata');
  expect(screen.getByRole('img', { name: 'The loop typeset in the manuscript' })).toHaveAttribute('src', figure);
  expect(screen.getByText('The same paper figure and its source caption.').closest('figcaption')).not.toBeNull();
  expect(screen.getByText('Undated Oxford notes')).toBeInTheDocument();
  expect(screen.getByText('The paired rank-growth invariant.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Reviewed source records and manuscript bindings' })).toHaveAttribute('href', 'https://example.org/references.json');
});

it('reflects changed manuscript prose without preserving an independent result interpretation', async () => {
  const payload = reading();
  payload.abstract = 'Revised abstract supplied by the paper.';
  payload.sections[1].blocks = [{ kind: 'markdown', content: '**Revised result.** A separately edited manuscript conclusion.' }];
  mockPaper(payload);
  render(<App />);
  expect(await screen.findByText('Revised abstract supplied by the paper.')).toBeInTheDocument();
  expect(screen.getByText(/A separately edited manuscript conclusion/)).toBeInTheDocument();
  expect(screen.queryByText('Manuscript abstract: a bounded comparison of retained tests.')).toBeNull();
  expect(screen.queryByText('Manuscript control')).toBeNull();
  expect(screen.queryByText('11395')).toBeNull();
  expect(screen.queryByText(/learned testing methods have not beaten/)).toBeNull();
});


it('does not substitute an older narrative when the current paper fails to load', async () => {
  mockPaper();
  const original = globalThis.fetch;
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/api/v1/paper')
    ? new Response('unavailable', { status: 500 }) : original(input)) as typeof fetch;
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('The paper could not be loaded');
  expect(screen.queryByText(/An AI can suggest a repair/)).toBeNull();
  expect(screen.getByRole('link', { name: 'Read the manuscript source' })).toHaveAttribute('href', 'https://github.com/wcook04/plectis-zenith/blob/main/paper/zenith.tex');
});


it('links the continuation guide and measurements among the current studies', async () => {
  mockPaper();
  render(<App />);
  await screen.findByRole('heading', { name: 'Current experiment records' });
  const guide = screen.getByText('Method, results and replay');
  const item = guide.closest('li')!;
  expect(item).toHaveTextContent('Continuation learner');
  expect(within(item).getByRole('link', { name: 'Saved measurements (JSON)' }))
    .toHaveAttribute('href', '/api/v1/evidence/continuation-learner');
  expect(item.closest('details')).toBeNull();
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith('/documents/continuation-learner'))).toBe(false);
  fireEvent.click(guide);
  expect(await screen.findByText('Reproduce the saved continuation learner.')).toBeInTheDocument();
});


it('preserves table focus when surrounding manuscript content rerenders', () => {
  const body = '| Method | Faults |\n| --- | --- |\n| Retained tester | 3 |';
  const { rerender } = render(<Markdown source={'First paragraph.\n\n' + body} base={source.url} />);
  const table = screen.getByRole('table');
  table.focus();
  rerender(<Markdown source={'Revised paragraph.\n\n' + body} base={source.url} />);
  expect(screen.getByRole('table')).toBe(table);
  expect(table).toHaveFocus();
});
