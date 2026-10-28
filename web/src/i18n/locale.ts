// Interface language: Paraglide holds the active locale; the user's choice is also saved as
// the server setting `ui.locale`, so it follows the account to other devices. Switching
// notifies subscribers (the app root re-renders every page in the new language at once).
import { getLocale, locales, setLocale } from '../paraglide/runtime.js'

export type Locale = (typeof locales)[number]
export const LOCALES: readonly Locale[] = locales

const listeners = new Set<() => void>()

export function currentLocale(): Locale {
  return getLocale()
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (locales as readonly string[]).includes(value)
}

/** Switch without a page reload; does nothing when `locale` is already active. */
export function changeLocale(locale: Locale): void {
  if (locale === getLocale()) return
  void setLocale(locale, { reload: false })
  document.documentElement.lang = locale
  listeners.forEach((fn) => fn())
}

export function subscribeLocale(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
