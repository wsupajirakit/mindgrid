import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Input, Switch } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { sourceText } from '../../../i18n/enums.ts'
import { settingLabel, settingValueLabel } from '../../../i18n/settings.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { putSetting, settingsQuery, type SettingsScope } from '../api.ts'

type Schema = { enum?: unknown[], type?: string }

function choicesOf(schema: Record<string, unknown>): string[] | null {
  const values = (schema as Schema).enum
  return Array.isArray(values) ? values.map(String) : null
}

/** Every setting declared for the scope, each with the control its schema calls for. */
export function SettingsPanel({ scope }: { scope: SettingsScope }) {
  const query = useQuery(settingsQuery(scope))
  const queryClient = useQueryClient()
  const { run } = useAction()
  const save = (key: string, value: unknown) => run(async () => {
    await putSetting(scope, key, value)
    await queryClient.invalidateQueries({ queryKey: settingsQuery(scope).queryKey })
  })
  if (query.error) return <Notice tone="error">{errorText(query.error)}</Notice>
  if (!query.data) return <Skeleton className="h-40" />
  return (
    <ul className="divide-y divide-border">
      {query.data.map((setting) => {
        const choices = choicesOf(setting.schema)
        const label = settingLabel(setting.key)
        return (
          <li key={setting.key} className="flex flex-wrap items-center gap-4 py-4 first:pt-0
            last:pb-0">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{label}</p>
              <p className="mt-1">
                <Badge>{m.setting_source({ source: sourceText(setting.source) })}</Badge>
              </p>
            </div>
            <div className="w-full sm:w-64">
              {choices ? (
                <Select aria-label={label} value={String(setting.value)}
                  onChange={(v) => void save(setting.key, v)}
                  options={choices.map((c) => ({ value: c,
                    label: settingValueLabel(setting.key, c) }))} />
              ) : (setting.schema as Schema).type === 'boolean' ? (
                <div className="flex justify-end">
                  <Switch label={label} checked={setting.value === true}
                    onChange={(v) => void save(setting.key, v)} />
                </div>
              ) : (
                <Input aria-label={label} defaultValue={String(setting.value ?? '')}
                  onBlur={(e) => {
                    const next = e.target.value
                    if (next !== String(setting.value ?? '')) void save(setting.key, next)
                  }} />
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
