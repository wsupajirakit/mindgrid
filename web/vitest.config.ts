import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.ts'

export default defineConfig((env) => mergeConfig(viteConfig(env), defineConfig({
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    // https: browsers (and jsdom) accept __Host- cookies only on secure origins.
    environmentOptions: { jsdom: { url: 'https://localhost/' } },
    setupFiles: ['src/testing/mocks/testServer.ts'],
  },
})))
