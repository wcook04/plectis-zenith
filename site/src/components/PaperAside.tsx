// The paper and evidence column beside each chapter: the manuscript section,
// its citations and the receipts bound to the chapter by /api/v1/site.
import type { Chapter, Paper } from '../api';
import { apiUrl } from '../api';
import { SECTION_LABEL } from '../content/copy';
import { sectionTitle, shortCitation } from '../lib/latex';

const EVIDENCE_LABEL: Record<string, string> = {
  'progress-campaign': 'Program-repair comparison',
  sources: 'Where each input comes from, with file hashes',
  observations: 'Synthetic observations, earlier and later',
  'window-result': 'Window experiment record',
  'conditional-result': 'Conditional continuation record',
  replacements: 'Synthetic multi-feed observations',
  'demo-result': 'Preparation record',
};

export function PaperAside({ chapter, paper, latex }: { chapter: Chapter; paper: Paper | null; latex: string | null }) {
  const section = chapter.paper_section;
  const currentPdf = paper !== null && 'pdf_current' in paper && paper.pdf_current === true;
  const citations = section && paper ? paper.citations.filter((c) => section.citation_ids.includes(c.id)) : [];
  return (
    <aside className="paper-aside" aria-label={`Sources for ${chapter.title}`}>
      {section && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">In the paper</h3>
          <p>
            <a href={section.source_url} target="_blank" rel="noreferrer">
              {(latex && sectionTitle(latex, section.start_line, section.end_line)) ?? SECTION_LABEL[section.id] ?? 'Paper section'}
            </a>
            <span className="paper-aside__quiet">
              {' '}
              (paper text and formatting code, lines {section.start_line}&ndash;{section.end_line})
            </span>
            {currentPdf && <><br /><a href={apiUrl(section.pdf_url)} target="_blank" rel="noreferrer">Section PDF</a></>}
          </p>
        </div>
      )}
      {citations.length > 0 && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">Cited here</h3>
          <ul className="refs refs--short">
            {citations.map((citation) => (
              <li key={citation.id}>
                <a href={`#ref-${citation.id}`}>{shortCitation(citation.latex)}</a>
              </li>
            ))}
          </ul>
        </div>
      )}
      {chapter.evidence_urls.length > 0 && (
        <div className="paper-aside__block">
          <h3 className="paper-aside__head">Saved experiment results</h3>
          <ul className="plain-list">
            {chapter.evidence_urls.map((url) => {
              const id = url.split('/').pop() ?? url;
              return (
                <li key={url}>
                  <a href={apiUrl(url)} target="_blank" rel="noreferrer">
                    {EVIDENCE_LABEL[id] ?? id}
                  </a>
                  <span className="paper-aside__quiet"> (JSON data file)</span>
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
  if (url.includes('github.com/wcook04/plectis-zenith')) {
    const file = url.split('/').pop()?.split('#')[0] ?? '';
    return file ? file : 'Repository';
  }
  if (url.includes('github.com')) return 'GitHub';
  return 'Link';
}
