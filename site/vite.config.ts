/// <reference types="vitest/config" />
import { readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

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
  plugins: [react(), publicManifest()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: backend, changeOrigin: false },
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
