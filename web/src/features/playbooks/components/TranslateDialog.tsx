import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { LOCALES } from '../../../i18n/locale.ts'
import { m } from '../../../paraglide/messages.js'
import { type PlaybookRow, saveTranslation } from '../api.ts'

const LANG: Record<string, () => string> = {
  en: () => m.lang_en(), th: () => m.lang_th(), it: () => m.lang_it(),
}
const OTHER = LOCALES.filter((l) => l !== 'en')

/** A superadmin edits a playbook's title and summary in another language (stored in the
 * database); empty fields bring back the shipped translation. */
export function TranslateDialog({ playbook, onClose }: { playbook: PlaybookRow,
  onClose: () => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [locale, setLocale] = useState<string>(OTHER[0] ?? 'th')
  const current = playbook.translations?.[locale]
  const [form, setForm] = useState({ title: current?.title ?? '', summary: current?.summary ?? '' })
  const pick = (next: string) => {
    const t = playbook.translations?.[next]
    setLocale(next)
    setForm({ title: t?.title ?? '', summary: t?.summary ?? '' })
  }
  const save = async () => {
    const ok = await run(async () => {
      await saveTranslation(playbook.id, locale, form.title, form.summary)
      await queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
    }, m.pb_translate_saved())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="lg"
      title={m.pb_translate_title({ title: playbook.title })} description={m.pb_translate_hint()}
      submitLabel={m.action_save()} busy={busy} disabled={!!form.summary && !form.title}
      onSubmit={save}>
      <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
        <p className="text-xs font-medium text-muted-foreground">{m.pb_original()}</p>
        <p className="mt-1 font-medium">{playbook.title}</p>
        <p className="mt-1 text-muted-foreground">{playbook.summary}</p>
      </div>
      <Field label={m.pb_language()}>
        <Select value={locale} onChange={pick}
          options={OTHER.map((l) => ({ value: l, label: LANG[l]?.() ?? l }))} />
      </Field>
      <Field label={m.pb_title()}>
        <Input value={form.title} maxLength={200}
          onChange={(e) => setForm({ ...form, title: e.target.value })} />
      </Field>
      <Field label={m.pb_summary()}>
        <Textarea rows={5} value={form.summary} maxLength={2000}
          onChange={(e) => setForm({ ...form, summary: e.target.value })} />
      </Field>
    </FormModal>
  )
}
