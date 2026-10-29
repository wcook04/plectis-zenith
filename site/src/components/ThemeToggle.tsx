import { useEffect, useState } from 'react';

type Theme = 'light' | 'dark' | null;

function read(): Theme {
  try {
    const value = window.localStorage.getItem('zenith-theme');
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.dataset.theme = theme;
    else delete root.dataset.theme;
    try {
      if (theme) window.localStorage.setItem('zenith-theme', theme);
      else window.localStorage.removeItem('zenith-theme');
    } catch {
      // storage unavailable
    }
  }, [theme]);
  const systemDark = typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  const effective = theme ?? (systemDark ? 'dark' : 'light');
  // The flip never smears: while the scheme changes no colour transition runs
  // (html.vt-theme in site.css), so links with a hover transition, such as the
  // shared header lockup and film still, change colour at once. Adapted from
  // the Plectis site's quiet flip (sites/microcosm/assets/docs.js).
  const flip = () => {
    const next = effective === 'dark' ? 'light' : 'dark';
    const root = document.documentElement;
    root.classList.add('vt-theme');
    root.dataset.theme = next;
    void root.offsetWidth;
    const lift = () => root.classList.remove('vt-theme');
    if (window.requestAnimationFrame) window.requestAnimationFrame(() => window.requestAnimationFrame(lift));
    else window.setTimeout(lift, 50);
    setTheme(next);
  };
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={effective === 'dark' ? 'Use light theme' : 'Use dark theme'}
      onClick={flip}
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
        <circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor" />
      </svg>
    </button>
  );
}
