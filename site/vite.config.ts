/// <reference types="vitest/config" />
import { readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { FAMILY, isReleased, siteFilms, spokenDuration } from './src/content/family';

// Without JavaScript the reading page cannot render, so index.html's noscript
// note carries the way back to Will Cook's home page and this site's films,
// written from the same family.json at build time (wcook04.github.io
// docs/family.md: no page depends on JavaScript to show its films).
function familyNoscript(): Plugin {
  const esc = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return {
    name: 'zenith-family-noscript',
    transformIndexHtml(html) {
      const home = esc(FAMILY.owner.home);
      const films = siteFilms().filter(isReleased).map(film => `<a href="${esc(film.youtube)}">${esc(film.title)}</a>`
        + ` (video on YouTube, ${spokenDuration(film.duration_seconds)})`);
      const text = [`Zenith, one of <a href="${home}" rel="author">${esc(FAMILY.owner.name)}'s websites</a>.`,
        ...(films.length ? [`Film: ${films.join('; ')}.`] : []),
        `<a href="${home}">All websites and films</a>.`].join(' ');
      return html.replace('<!-- family links -->', `<p>${text}</p>`);
    },
  };
}

// The Python backend serves only the files listed in zenith-public.json
// (docs/website-backend.md), so the build writes that list from what it emitted.
function publicManifest(): Plugin {
  let outDir = 'dist';
  return {
    name: 'zenith-public-manifest',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir;
    },
    closeBundle() {
      const files: string[] = [];
      const walk = (dir: string) => {
        for (const name of readdirSync(dir)) {
          if (name.startsWith('.')) continue;
          const path = join(dir, name);
          if (statSync(path).isDirectory()) walk(path);
          else files.push(relative(outDir, path).split(sep).join('/'));
        }
      };
      walk(outDir);
      const listed = files.filter((file) => file !== 'zenith-public.json').sort();
      writeFileSync(join(outDir, 'zenith-public.json'), `${JSON.stringify({ files: listed }, null, 2)}\n`);
    },
  };
}

const backend = process.env.ZENITH_API ?? 'http://127.0.0.1:4175';

export default defineConfig({
  plugins: [react(), familyNoscript(), publicManifest()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: backend, changeOrigin: false },
      '/assets/repair-loop.svg': { target: backend, changeOrigin: false },
      '/assets/paper.pdf': { target: backend, changeOrigin: false },
      '/assets/graphs': { target: backend, changeOrigin: false },
    },
  },
  build: {
    // The backend reserves /assets/paper.pdf and /assets/graphs, so emitted
    // bundles live under their own directory.
    assetsDir: 'static',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          graph: ['reactflow'],
          markdown: ['react-markdown', 'remark-gfm'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    css: false,
  },
});
