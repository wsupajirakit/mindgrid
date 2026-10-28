import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { suggestSlug } from '../../../utils/slug.ts'
import { createProject } from '../api.ts'

export const SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/
const EMPTY = { slug: '', name: '', description: '' }

/** New project, in a modal. The short name is suggested from the name until edited. */
export function NewProjectDialog({ open, onOpenChange }: { open: boolean,
  onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState(EMPTY)
  const [slugEdited, setSlugEdited] = useState(false)
  const slugBad = form.slug !== '' && !SLUG.test(form.slug)
  const save = async () => {
    const ok = await run(async () => {
      await createProject(form.slug, form.name, form.description)
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
    }, m.projects_created())
    if (ok) { setForm(EMPTY); setSlugEdited(false); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.projects_new()}
      submitLabel={m.action_create()} busy={busy}
      disabled={!form.name.trim() || !SLUG.test(form.slug)} onSubmit={save}>
      <Field label={m.col_name()}>
        <Input value={form.name} maxLength={120} autoFocus onChange={(e) => setForm({
          ...form, name: e.target.value,
          slug: slugEdited ? form.slug : suggestSlug(e.target.value),
        })} />
      </Field>
      <Field label={m.col_slug()} error={slugBad ? m.err_slug_invalid() : undefined}>
        <Input value={form.slug} onChange={(e) => {
          setSlugEdited(true); setForm({ ...form, slug: e.target.value })
        }} />
      </Field>
      <Field label={m.col_description()}>
        <Textarea rows={3} maxLength={2000} value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </Field>
    </FormModal>
  )
}
