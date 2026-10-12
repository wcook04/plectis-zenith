// The paper and evidence column beside each chapter: the manuscript section,
// its citations and the receipts bound to the chapter by /api/v1/site.
import type { Chapter, Paper } from '../api';
import { apiUrl } from '../api';
import { EVIDENCE_KIND_LABEL, SECTION_LABEL } from '../content/copy';
import { latexToText } from '../lib/latex';

const EVIDENCE_LABEL: Record<string, string> = {
  sources: 'Source hashes for the saved feeds',
  observations: 'Example stored prices, earlier and later',
  'window-result': 'Window experiment receipt',
  'conditional-result': 'Conditional continuation receipt',
  replacements: 'Synthetic macro and news examples',
  'demo-result': 'Preparation receipt',
};

export function PaperAside({ chapter, paper }: { chapter: Chapter; paper: Paper | null }) {
  const section = chapter.paper_section;
  const kind = EVIDENCE_KIND_LABEL[chapter.evidence_kind];
  const citations = section && paper ? paper.citations.filter((c) => section.citation_ids.includes(c.id)) : [];
  return (
    <aside className="paper-aside" aria-label={`Sources for ${chapter.title}`}>
      {kind && (
        <p className={`kind kind--${chapter.evidence_kind}`}>
          <span className="kind__label">{kind.label}.</span> {kind.note}
        </p>
      )}
      {section && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">In the paper</h3>
          <p>
            <a href={apiUrl(section.pdf_url)} target="_blank" rel="noreferrer">
              {SECTION_LABEL[section.id] ?? 'Paper section'}
            </a>
            <span className="paper-aside__quiet">
              {' '}
              (PDF), or the{' '}
              <a href={section.source_url} target="_blank" rel="noreferrer">
                LaTeX source, lines {section.start_line}&ndash;{section.end_line}
              </a>
            </span>
          </p>
        </div>
      )}
      {citations.length > 0 && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">Cited here</h3>
          <ol className="refs">
            {citations.map((citation) => (
              <li key={citation.id} id={`ref-${chapter.id}-${citation.id}`}>
                {latexToText(citation.latex)}
                {citation.urls.map((url) => (
                  <a key={url} className="refs__link" href={url} target="_blank" rel="noreferrer">
                    {linkLabel(url)}
                  </a>
                ))}
              </li>
            ))}
          </ol>
        </div>
      )}
      {chapter.evidence_urls.length > 0 && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">Evidence</h3>
          <ul className="plain-list">
            {chapter.evidence_urls.map((url) => {
              const id = url.split('/').pop() ?? url;
              return (
                <li key={url}>
                  <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                    {EVIDENCE_LABEL[id] ?? id}
                  </a>
                  <span className="paper-aside__quiet"> (JSON)</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </aside>
  );
}

export function linkLabel(url: string): string {
  if (url.includes('arxiv.org')) return 'arXiv';
  if (url.includes('doi.org')) return 'DOI';
  if (url.includes('github.com/wcook04/plectis-zenith')) return 'Repository';
  if (url.includes('github.com')) return 'GitHub';
  return 'Link';
}
