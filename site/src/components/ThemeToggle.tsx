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
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={effective === 'dark' ? 'Use light theme' : 'Use dark theme'}
      onClick={() => setTheme(effective === 'dark' ? 'light' : 'dark')}
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
        <circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor" />
      </svg>
    </button>
  );
}
