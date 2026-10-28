import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { addSource, check, sourcesQuery, templatesQuery } from '../api.ts'

export type Target = { projectId: string, categoryId: string, label: string }
const EMPTY = { name: '', path: '', mapping: '', target: '', every: '' }

/** A new source: the repository folder, where accepted knowledge goes, and the mapping. */
export function SourceDialog({ targets, open, onOpenChange }: { targets: Target[],
  open: boolean, onOpenChange: (open: boolean) => void }) {
  const templates = useQuery(templatesQuery)
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState(EMPTY)
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v })
  const save = async () => {
    const target = targets.find((t) => `${t.projectId}/${t.categoryId}` === form.target)
    const ok = await run(async () => {
      await addSource({ name: form.name, path: form.path, mapping: JSON.parse(form.mapping),
        project_id: target?.projectId ?? '', category_id: target?.categoryId ?? '',
        every_minutes: form.every === '' ? null : Number(form.every) })
      await queryClient.invalidateQueries({ queryKey: sourcesQuery.queryKey })
    }, m.syn_added())
    if (ok) { setForm(EMPTY); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} size="lg" title={m.syn_new()}
      description={m.syn_intro()} submitLabel={m.action_add()} busy={busy}
      disabled={!form.name || !form.path || !form.target || !form.mapping} onSubmit={save}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={m.col_name()}>
          <Input value={form.name} autoFocus onChange={(e) => set('name', e.target.value)} />
        </Field>
        <Field label={m.syn_path()}>
          <Input value={form.path} onChange={(e) => set('path', e.target.value)} />
        </Field>
        <Field label={m.syn_target()}>
          <Select value={form.target} onChange={(v) => set('target', v)} placeholder="—"
            options={targets.map((t) => ({ value: `${t.projectId}/${t.categoryId}`,
              label: t.label }))} />
        </Field>
        <Field label={m.conn_every()}>
          <Input inputMode="numeric" value={form.every}
            onChange={(e) => set('every', e.target.value)} />
        </Field>
      </div>
      <Field label={m.conn_template()}>
        <Select placeholder="—" onChange={(v) => {
          const t = templates.data?.find((x) => x.id === v)
          if (t) set('mapping', JSON.stringify(t.mapping, null, 2))
        }} options={(templates.data ?? []).map((t) => ({ value: t.id, label: t.title }))} />
      </Field>
      <Field label={m.syn_mapping()}>
        <Textarea rows={10} className="font-mono text-xs" value={form.mapping}
          onChange={(e) => set('mapping', e.target.value)} />
      </Field>
    </FormModal>
  )
}

/** Check a source now; on its first check it may propose every file. */
export function CheckDialog({ source, onClose }: { source: { id: string, name: string },
  onClose: () => void }) {
  const { busy, run } = useAction()
  const [importAll, setImportAll] = useState(false)
  const send = async () => {
    if (await run(() => check(source.id, importAll), m.syn_checked())) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="sm"
      title={m.syn_check_title({ name: source.name })} description={m.syn_check_text()}
      submitLabel={m.syn_check()} busy={busy} onSubmit={send}>
      <Checkbox checked={importAll} onChange={setImportAll} label={m.syn_import_all()} />
    </FormModal>
  )
}
