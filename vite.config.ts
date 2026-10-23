import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Injects the resolved base path into the GitHub Pages SPA fallback page.
 *
 * `public/404.html` redirects unknown deep links to the site root, so it must
 * know the real base path. Vite does not transform files in `public/`, hence
 * this small post-build step: it keeps project sites, custom domains and
 * repository renames working without hand-editing the fallback.
 */
function spaFallbackPlugin(base: string): Plugin {
  return {
    name: 'chad-spa-fallback',
    apply: 'build',
    closeBundle() {
      const file = resolve(process.cwd(), 'dist/404.html')
      if (!existsSync(file)) return
      const normalised = base.endsWith('/') ? base : `${base}/`
      writeFileSync(file, readFileSync(file, 'utf8').replaceAll('__CHAD_BASE__', normalised))
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1]
  const base =
    env.VITE_BASE_PATH ||
    (process.env.GITHUB_ACTIONS && repoName ? `/${repoName}/` : '/')

  return {
    base,
    plugins: [react(), tailwindcss(), spaFallbackPlugin(base)],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      target: 'es2022',
      sourcemap: false,
      chunkSizeWarningLimit: 800,
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      // The Arena live preview is served from a proxied host.
      allowedHosts: true,
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
      strictPort: true,
      allowedHosts: true,
    },
  }
})
