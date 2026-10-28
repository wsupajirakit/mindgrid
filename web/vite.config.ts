import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import { paraglideVitePlugin } from '@inlang/paraglide-js'
import { msw } from 'msw/vite'
import { readBuildEnv } from './build-env.ts'
import { paraglideOptions } from './i18n.config.ts'

const env = readBuildEnv()

export default defineConfig(({ mode }) => ({
  base: env.APP_BASE,
  define: {
    __APP_API_BASE__: JSON.stringify(env.APP_API_BASE),
  },
  plugins: [
    // File routes are the page views (src/pages); the generated tree lives with the router.
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routesDirectory: './src/pages',
      generatedRouteTree: './src/app/routeTree.gen.ts',
    }),
    paraglideVitePlugin({ ...paraglideOptions, strategy: [...paraglideOptions.strategy] }),
    react(),
    tailwindcss(),
    // Mock mode only: serves the MSW worker script; never part of a production build.
    mode === 'mock' && msw({ mode: 'worker-only' }),
  ],
  build: {
    sourcemap: false,
    manifest: true,
    rolldownOptions: {
      output: {
        codeSplitting: {
          // Without this, Rolldown merges zod/mini (used only by lazy pages) into the chunk the
          // entry imports for React, so it loaded on first paint. Its own chunk is lazy and
          // cache-stable: it changes only when zod is upgraded.
          groups: [{ name: 'zod', test: /[\\/]node_modules[\\/]zod[\\/]/ }],
        },
      },
    },
  },
}))
