// Markdown from the backend is rendered as untrusted content: raw HTML is
// skipped, link and image URLs pass react-markdown's safe URL filter, and
// relative links resolve against the document's base_url.
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function resolveDocUrl(url: string, base: string): string {
  if (!url || url.startsWith('#')) return url;
  try {
    return new URL(url, base).toString();
  } catch {
    return '';
  }
}

export function Markdown({ source, base }: { source: string; base: string }) {
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
          img: ({ src, alt }) => (src ? <img src={String(src)} alt={alt ?? ''} loading="lazy" /> : null),
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
