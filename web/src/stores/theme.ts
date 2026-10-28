// Theme mode store. The initial value is applied before paint by public/theme-init.js.
export type ThemeMode = 'system' | 'light' | 'dark'
export const THEME_MODES: readonly ThemeMode[] = ['system', 'light', 'dark']

const STORAGE_KEY = 'mindgrid.theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')
const listeners = new Set<() => void>()

function readMode(): ThemeMode {
  const mode = document.documentElement.dataset.themeMode
  return mode === 'light' || mode === 'system' ? mode : 'dark'
}

function apply(mode: ThemeMode): void {
  const dark = mode === 'dark' || (mode === 'system' && media.matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.documentElement.dataset.themeMode = mode
  listeners.forEach((fn) => fn())
}

media.addEventListener('change', () => {
  if (readMode() === 'system') apply('system')
})

export function getThemeMode(): ThemeMode {
  return readMode()
}

/** Resolved theme ('light' | 'dark') used by charts. */
export function getResolvedTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function setThemeMode(mode: ThemeMode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // storage blocked: keep the mode for this document only
  }
  apply(mode)
}

export function subscribeTheme(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
