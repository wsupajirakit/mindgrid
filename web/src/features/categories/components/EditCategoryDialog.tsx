import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { categoriesQuery, type Category, updateCategory } from '../api.ts'

/** Rename a category, describe it, or restrict it (asks first: who can see it changes). */
export function EditCategoryDialog({ category, onClose }: { category: Category,
  onClose: () => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState({ name: category.name, description: category.description,
    restricted: category.restricted })
  const save = async () => {
    if (form.restricted !== category.restricted) {
      const ok = await confirm({
        title: form.restricted ? m.cat_restrict_title() : m.cat_open_title(),
        description: form.restricted ? m.cat_access_restricted() : m.cat_access_open(),
        confirmLabel: m.action_save(), tone: form.restricted ? 'destructive' : 'default' })
      if (!ok) return
    }
    const ok = await run(async () => {
      await updateCategory(category.id, form)
      await queryClient.invalidateQueries({
        queryKey: categoriesQuery(category.project_id).queryKey })
    }, m.cat_saved())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }}
      title={m.cat_edit({ name: category.name })} submitLabel={m.action_save()} busy={busy}
      disabled={!form.name.trim()} onSubmit={save}>
      <Field label={m.col_name()}>
        <Input value={form.name} autoFocus maxLength={120}
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label={m.col_description()}>
        <Textarea rows={3} value={form.description} maxLength={2000}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </Field>
      <Checkbox checked={form.restricted} label={m.category_restricted()}
        onChange={(v) => setForm({ ...form, restricted: v })} />
      <p className="text-xs text-muted-foreground">{m.cat_restricted_hint()}</p>
    </FormModal>
  )
}
