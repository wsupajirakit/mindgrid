// Navigation layout (side menu or top bar with a mega menu). The account's saved choice
// (`ui.layout`) is applied on sign-in; the last one is kept locally so the first paint
// already matches.
export type NavLayout = 'sidebar' | 'mega'

const STORAGE_KEY = 'mindgrid.layout'
const listeners = new Set<() => void>()

function read(): NavLayout {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'mega' ? 'mega' : 'sidebar'
  } catch {
    return 'sidebar'
  }
}

let current: NavLayout = read()

export const isNavLayout = (value: unknown): value is NavLayout =>
  value === 'sidebar' || value === 'mega'

export function getNavLayout(): NavLayout {
  return current
}

export function setNavLayout(layout: NavLayout): void {
  if (layout === current) return
  current = layout
  try {
    localStorage.setItem(STORAGE_KEY, layout)
  } catch {
    // storage blocked: keep the layout for this document only
  }
  listeners.forEach((fn) => fn())
}

export function subscribeNavLayout(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
