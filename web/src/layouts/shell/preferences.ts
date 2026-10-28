// The account's interface preferences (language, theme, menu layout): applied when they
// load, and saved back with the account when the user changes one.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { putSetting, settingsQuery } from '../../features/settings/api.ts'
import { changeLocale, isLocale } from '../../i18n/locale.ts'
import { isNavLayout, setNavLayout } from '../../stores/layout.ts'
import { setThemeMode, type ThemeMode } from '../../stores/theme.ts'

const MINE = settingsQuery({ kind: 'me' })
const THEMES: readonly string[] = ['system', 'light', 'dark']

export function useAccountPreferences() {
  const prefs = useQuery(MINE)
  useEffect(() => {
    for (const setting of prefs.data ?? []) {
      if (setting.key === 'ui.locale' && isLocale(setting.value)) changeLocale(setting.value)
      if (setting.key === 'ui.theme' && THEMES.includes(String(setting.value))) {
        setThemeMode(setting.value as ThemeMode)
      }
      if (setting.key === 'ui.layout' && isNavLayout(setting.value)) setNavLayout(setting.value)
    }
  }, [prefs.data])
}

type Key = 'ui.locale' | 'ui.theme' | 'ui.layout'

/** Saves one preference: the cached copy is updated first (so nothing re-applies the old
 * value while the request runs), then `apply` shows it, then the server stores it.
 * Resolves false when the server refused; the cache is reloaded from the server then. */
export function useSavePreference() {
  const queryClient = useQueryClient()
  return async (key: Key, value: string, apply: () => void) => {
    queryClient.setQueryData(MINE.queryKey, (rows) => rows?.map((r) => (
      r.key === key ? { ...r, value } : r)))
    apply()
    try {
      await putSetting({ kind: 'me' }, key, value)
      return true
    } catch {
      return false
    } finally {
      await queryClient.invalidateQueries({ queryKey: MINE.queryKey })
    }
  }
}
