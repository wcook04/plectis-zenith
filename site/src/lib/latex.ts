// Turn a bibliography entry's LaTeX into readable text. Links are kept as
// separate URLs on the citation record, so \href keeps only its label.
export function latexToText(latex: string): string {
  return latex
    .replace(/\\(?:emph|textit|textbf|texttt|path)\{([^}]*)\}/g, '$1')
    .replace(/\\href\{[^}]*\}\{([^}]*)\}/g, '$1')
    .replace(/``/g, '“')
    .replace(/''/g, '”')
    .replace(/---/g, '—')
    .replace(/--/g, '–')
    .replace(/~/g, ' ')
    .replace(/\\&/g, '&')
    .replace(/\\%/g, '%')
    .replace(/\\_/g, '_')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// A compact author-year label for the margin; the full entry stays in the
// bibliography at the end of the page.
export function shortCitation(latex: string): string {
  const text = latexToText(latex);
  const year = Array.from(text.matchAll(/\b(?:19|20)\d{2}\b(?!\.\d)/g)).at(-1)?.[0];
  const person = /^(?:[A-Z]\.\s?)+([A-Z][\w\u00C0-\u017F'-]+)(\s+et al\.)?/.exec(text);
  if (person) return `${person[1]}${person[2] ? ' et al.' : ''}${year ? ` ${year}` : ''}`;
  const [author, title] = text.split(/\.\s+/);
  const short = title ? title.split(/[:,]/)[0].replace(/\s+\d{1,2} \w+ \d{4}$/, '') : '';
  return `${author}${year ? ` ${year}` : ''}${short ? `: ${short}` : ''}`;
}

// "Section N, Title" for a manuscript line range, read from the LaTeX itself:
// the first numbered bold heading inside the range, else the last one before it.
export function sectionTitle(latex: string, startLine: number, endLine: number): string | null {
  const lines = latex.split('\n');
  const heading = (line: string) => /\\textbf\{(\d+)\.\s*([^}]*?)\.?\}/.exec(line);
  for (let i = startLine - 1; i < Math.min(endLine, lines.length); i++) {
    const m = heading(lines[i]);
    if (m) return `Section ${m[1]}, ${latexToText(m[2])}`;
  }
  for (let i = startLine - 2; i >= 0; i--) {
    const m = heading(lines[i]);
    if (m) return `Section ${m[1]}, ${latexToText(m[2])}`;
  }
  return null;
}
