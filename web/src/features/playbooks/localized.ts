// A playbook's title and summary in the interface language when it has a translation,
// otherwise the English base text; `locale` says which one is shown.
import { currentLocale } from '../../i18n/locale.ts'
import type { PlaybookRow } from './api.ts'

export function localized(p: PlaybookRow): { title: string, summary: string, locale: string } {
  const locale = currentLocale()
  const t = locale === 'en' ? undefined : p.translations?.[locale]
  return t ? { title: t.title, summary: t.summary || p.summary, locale }
    : { title: p.title, summary: p.summary, locale: 'en' }
}
