// Markdown from the backend is rendered as untrusted content: raw HTML is
// skipped, link and image URLs pass react-markdown's safe URL filter, and
// relative links resolve against the document's base_url.
import { useState } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiUrl } from '../api';
import { useSiteFigures } from '../lib/siteContext';

export function resolveDocUrl(url: string, base: string): string {
  if (!url || url.startsWith('#')) return url;
  try {
    return new URL(url, base).toString();
  } catch {
    return '';
  }
}

// Repository figures (docs/graphs/<id>.svg) resolve to GitHub HTML pages,
// which cannot render as images; the backend serves the same files under
// /assets/graphs/<id>.svg, listed in /site figures.
export function figureUrl(resolved: string, figures: Record<string, string>): string {
  const match = /\/graphs\/([\w-]+)\.svg(?:[?#].*)?$/.exec(resolved);
  if (match && figures[match[1]]) return apiUrl(figures[match[1]]);
  return resolved;
}

function DocImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="doc-figure-missing" role="note">
        Figure unavailable: {alt || 'untitled'}.{' '}
        <a href={src} target="_blank" rel="noreferrer">
          Open the source
        </a>
      </span>
    );
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}

export function Markdown({ source, base }: { source: string; base: string }) {
  const figures = useSiteFigures();
  return (
    <div className="prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={(url) => defaultUrlTransform(resolveDocUrl(url, base))}
        components={{
          a: ({ href, children }) => (
            <a href={href} target={href?.startsWith('#') ? undefined : '_blank'} rel="noreferrer">
              {children}
            </a>
          ),
          img: ({ src, alt }) => (src ? <DocImage src={figureUrl(String(src), figures)} alt={alt ?? ''} /> : null),
          table: ({ children }) => <table tabIndex={0}>{children}</table>,
          h1: ({ children }) => <h4>{children}</h4>,
          h2: ({ children }) => <h5>{children}</h5>,
          h3: ({ children }) => <h6>{children}</h6>,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
