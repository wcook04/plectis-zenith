// Typed read-only client for the Zenith website backend (docs/website-backend.md).
// The backend owns source fidelity; this module only fetches and caches.

export type Mission = 'lab' | 'oracle' | 'refinement';

export type SourceRef = { path: string; sha256: string; url: string };

export type PaperSection = {
  id: string;
  start_line: number;
  end_line: number;
  source: SourceRef;
  source_url: string;
  pdf_url: string;
  citation_ids: string[];
};

export type EvidenceKind =
  | 'proposed_process'
  | 'authored_mechanism'
  | 'measured_execution'
  | 'verified_preparation'
  | 'research_proposal';

export type Chapter = {
  id: string;
  title: string;
  evidence_kind: EvidenceKind;
  document_url: string | null;
  available: boolean;
  figure_url: string | null;
  graph_url: string | null;
  paper_section: PaperSection | null;
  evidence_urls: string[];
};

export type Site = {
  schema: string;
  title: string;
  paper_url: string;
  chapters: Chapter[];
  notice: string;
  notice_url: string;
  documents: Record<string, string>;
  figures: Record<string, string>;
  evidence: Record<string, string>;
  local_runs_enabled: boolean;
  run_index_url?: string | null;
  data_mode?: string;
  data_note?: string;
  capabilities: Record<string, boolean>;
};

export type Citation = {
  id: string;
  latex: string;
  urls: string[];
  used_at: { line: number }[];
};

export type Paper = {
  title: string;
  source: SourceRef;
  source_url: string;
  pdf_url: string;
  pdf_sha256: string;
  citations: Citation[];
  sections: PaperSection[];
  notice_url: string;
};

export type DocHeading = { level: number; title: string; line: number };

export type Doc = {
  id: string;
  format: 'markdown' | 'latex' | string;
  content: string;
  headings: DocHeading[];
  source: SourceRef;
  base_url: string;
};

export type GraphNode = {
  id: string;
  type: 'tool' | 'reasoning' | string;
  group: string;
  lane: string;
  purpose: string;
  mechanism: string;
  expectation: string;
  boundary: string;
  instruction: string;
  instruction_kind: string;
  dependencies: string[];
  consumers: string[];
  output_schema: string;
  source: SourceRef;
  explanation_url: string | null;
  demo_provenance?: Provenance | null;
  dossier?: { data: Record<string, unknown>; source: SourceRef } | null;
};

export type Provenance = {
  node_id: string;
  input_origin: 'real_saved_input' | 'authored_synthetic' | 'derived_synthetic_inputs' | string;
  input_sha256?: string;
  source_sha256?: string;
  public_payload?: string;
  permission_status?: string;
  dependencies?: string[];
};

export type GraphEdge = { id: string; source: string; target: string; kind: string };

export type Graph = {
  schema: string;
  mission: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  waves: string[][];
  node_count: number;
  edge_count: number;
  focus: { id: string | null; ancestors: string[]; descendants: string[] };
  semantics: string;
};

export type Evidence = { id: string; source: SourceRef; data: Record<string, unknown> };

export type RunOutcome = 'loaded' | 'success' | 'failure' | 'not_started' | string;

export type RunSummary = {
  run_id: string;
  mission: string;
  source_kind: string;
  subject_run: string | null;
  grade: string;
  grade_reason: string;
  timestamp: number;
  node_outcomes: Record<string, RunOutcome>;
};

export type RunIndex = { runs: RunSummary[]; total: number; limit: number; offset: number };

export type Attempt = {
  attempt: number;
  status: string;
  error_class?: string | null;
  errors?: string[];
  json_error?: string | null;
  prompt_sha256?: string;
  prompt_length?: number;
  prompt_snippet?: string;
  prompt_truncated?: boolean;
  output_length?: number;
  output_text?: string;
  output_truncated?: boolean;
};

export type RunNode = {
  run_id: string;
  node_id: string;
  status: RunOutcome;
  source_kind: string;
  subject_run: string | null;
  artifact: {
    status: string;
    timestamp?: number;
    metadata?: { error?: string | null; hydrated_from?: string | null; input_node_ids?: string[] };
    data?: unknown;
  } | null;
  artifact_bytes: number | null;
  artifact_omitted: boolean;
  artifact_error: 'missing' | 'malformed' | 'unsafe' | 'oversized' | string | null;
  attempts: Attempt[];
};

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// Same-origin by default: Vite proxies /api in development and the Python
// server mounts the build in production. VITE_ZENITH_API overrides it.
export const API_BASE: string = (import.meta.env.VITE_ZENITH_API as string | undefined) ?? '';

export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE}${path}`;
}

const cache = new Map<string, Promise<unknown>>();

async function fetchJson<T>(path: string, { fresh = false }: { fresh?: boolean } = {}): Promise<T> {
  const url = apiUrl(path);
  if (!fresh && cache.has(url)) return cache.get(url) as Promise<T>;
  const request = (async () => {
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
      let code = 'http_error';
      let message = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        code = String(body?.error ?? body?.code ?? code);
        message = String(body?.message ?? body?.detail ?? message);
      } catch {
        // body was not JSON
      }
      throw new ApiError(response.status, code, message);
    }
    return (await response.json()) as T;
  })();
  if (!fresh) {
    cache.set(url, request);
    request.catch(() => cache.delete(url));
  }
  return request;
}

export const api = {
  site: () => fetchJson<Site>('/api/v1/site'),
  paper: () => fetchJson<Paper>('/api/v1/paper'),
  document: (url: string) => fetchJson<Doc>(url),
  graph: (url: string) => fetchJson<Graph>(url),
  node: (id: string) => fetchJson<GraphNode>(`/api/v1/nodes/${encodeURIComponent(id)}`),
  evidence: (url: string) => fetchJson<Evidence>(url),
  runs: (query: { q?: string; mission?: string; limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== '') params.set(key, String(value));
    });
    const suffix = params.toString() ? `?${params}` : '';
    return fetchJson<RunIndex>(`/api/v1/runs${suffix}`, { fresh: true });
  },
  // Local results carry Cache-Control: no-store; keep them out of the memo too.
  runNode: (runId: string, nodeId: string) =>
    fetchJson<RunNode>(
      `/api/v1/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}`,
      { fresh: true },
    ),
};

export function clearApiCache() {
  cache.clear();
}
