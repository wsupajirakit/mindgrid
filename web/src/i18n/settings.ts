// Labels for declared settings and their values (explicit maps, one message each).
import { m } from '../paraglide/messages.js'

const LABELS: Record<string, () => string> = {
  'ui.locale': () => m.setting_ui_locale(),
  'ui.theme': () => m.setting_ui_theme(),
}
// Language names are shown in their own language, the convention for language pickers.
const LANGUAGE: Record<string, string> = { en: 'English', th: 'ไทย', it: 'Italiano' }
const VALUES: Record<string, Record<string, () => string>> = {
  'ui.theme': { system: () => m.theme_system(), light: () => m.theme_light(),
    dark: () => m.theme_dark() },
}

export const settingLabel = (key: string) => LABELS[key]?.() ?? key

export function settingValueLabel(key: string, value: string): string {
  if (key === 'ui.locale') return LANGUAGE[value] ?? value
  return VALUES[key]?.[value]?.() ?? value
}
