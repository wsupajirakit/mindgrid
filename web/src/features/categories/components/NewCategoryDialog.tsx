import { useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, Input } from '../../../components/ui/Field.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { suggestSlug } from '../../../utils/slug.ts'
import { categoriesQuery, createCategory } from '../api.ts'

const EMPTY = { slug: '', name: '', restricted: false }
const SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/

/** New category, in a modal; the short name is suggested from the name until edited. */
export function NewCategoryDialog({ projectId, open, onOpenChange }: { projectId: string,
  open: boolean, onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState(EMPTY)
  const [slugEdited, setSlugEdited] = useState(false)
  const save = async () => {
    const ok = await run(async () => {
      await createCategory(projectId, form.slug, form.name, form.restricted)
      await queryClient.invalidateQueries({ queryKey: categoriesQuery(projectId).queryKey })
    }, m.cat_created())
    if (ok) { setForm(EMPTY); setSlugEdited(false); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.cat_new()}
      submitLabel={m.action_create()} busy={busy}
      disabled={!form.name.trim() || !SLUG.test(form.slug)} onSubmit={save}>
      <Field label={m.col_name()}>
        <Input value={form.name} autoFocus onChange={(e) => setForm({ ...form,
          name: e.target.value, slug: slugEdited ? form.slug : suggestSlug(e.target.value) })} />
      </Field>
      <Field label={m.col_slug()} error={form.slug && !SLUG.test(form.slug)
        ? m.err_slug_invalid() : undefined}>
        <Input value={form.slug} onChange={(e) => {
          setSlugEdited(true)
          setForm({ ...form, slug: e.target.value.toLowerCase() })
        }} />
      </Field>
      <Checkbox checked={form.restricted} label={m.category_restricted()}
        onChange={(v) => setForm({ ...form, restricted: v })} />
      <p className="text-xs text-muted-foreground">{m.cat_restricted_hint()}</p>
    </FormModal>
  )
}

/** A "new category" button with its modal (also offered where knowledge has no category). */
export function NewCategoryButton({ projectId, size }: { projectId: string,
  size?: 'sm' | 'default' }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button size={size} onClick={() => setOpen(true)}><Plus />{m.cat_new()}</Button>
      <NewCategoryDialog projectId={projectId} open={open} onOpenChange={setOpen} />
    </>
  )
}
