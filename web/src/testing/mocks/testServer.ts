// Vitest setup: every request goes through MSW; an unhandled request fails the test.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { base, handlers, ME, resetMockState } from './handlers.ts'

// jsdom has no ResizeObserver; Radix measures controls with it.
globalThis.ResizeObserver ??= class {
  observe() { /* nothing to measure in jsdom */ }
  unobserve() { /* idem */ }
  disconnect() { /* idem */ }
}

// jsdom has no matchMedia; the theme store listens to the system colour scheme.
window.matchMedia ??= (query: string) => ({
  matches: false, media: query, onchange: null,
  addEventListener: () => undefined, removeEventListener: () => undefined,
  addListener: () => undefined, removeListener: () => undefined, dispatchEvent: () => false,
})

// jsdom lacks pointer capture and scrollIntoView; Radix Select calls both.
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.releasePointerCapture ??= () => undefined
Element.prototype.scrollIntoView ??= () => undefined

export const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => { server.resetHandlers(); cleanup(); resetMockState() })
afterAll(() => server.close())

/** Hold sign-in answers until the returned function is called (a slow server); calling it
 * before the request arrives works too. */
export function holdSignIn(): () => void {
  let release = (): void => undefined
  const gate = new Promise<void>((resolve) => { release = resolve })
  server.use(http.post(`${base}/auth/sign-in`, async () => {
    await gate
    return HttpResponse.json(ME)
  }))
  return release
}
