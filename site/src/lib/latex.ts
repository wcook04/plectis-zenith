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
