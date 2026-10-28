// Locale-aware formatting (the interface language decides the format).
import { useMemo } from 'react'
import { getLocale } from '../paraglide/runtime.js'

export function useFormat() {
  const locale = getLocale()
  return useMemo(() => {
    const dt = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' })
    return { dateTime: (iso: string) => dt.format(new Date(iso)) }
  }, [locale])
}
