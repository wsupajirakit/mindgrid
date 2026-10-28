// Re-renders the whole app in the new language the moment the locale changes: the key
// remounts the tree under it (cached queries and the router state are kept).
import { Fragment, type ReactNode, useSyncExternalStore } from 'react'
import { currentLocale, subscribeLocale } from '../i18n/locale.ts'

export function LocaleRoot({ children }: { children: ReactNode }) {
  const locale = useSyncExternalStore(subscribeLocale, currentLocale)
  return <Fragment key={locale}>{children}</Fragment>
}
