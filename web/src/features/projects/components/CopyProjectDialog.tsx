import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, FieldGroup } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { copyProject, projectCategoriesQuery, projectsQuery } from '../api.ts'

function CopyDialog({ projectId, onClose }: { projectId: string, onClose: () => void }) {
  const projects = useQuery(projectsQuery())
  const categories = useQuery(projectCategoriesQuery(projectId))
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [target, setTarget] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [playbooks, setPlaybooks] = useState(true)
  const save = async () => {
    let summary = ''
    const ok = await run(async () => {
      const done = await copyProject(projectId, target, picked, playbooks)
      summary = m.copy_done_text({ categories: String(done.categories),
        documents: String(done.documents), playbooks: String(done.playbooks) })
      await queryClient.invalidateQueries({ queryKey: ['projects', target] })
    }, () => summary)
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="lg"
      title={m.copy_title()} description={m.copy_intro()} submitLabel={m.copy_submit()}
      busy={busy} disabled={!target || (picked.length === 0 && !playbooks)} onSubmit={save}>
      <Field label={m.copy_target()}>
        <Select value={target} onChange={setTarget} placeholder="—"
          options={(projects.data ?? []).filter((p) => p.id !== projectId)
            .map((p) => ({ value: p.id, label: p.name }))} />
      </Field>
      <FieldGroup label={m.copy_categories()} hint={m.copy_categories_hint()}>
        {(categories.data ?? []).length === 0 ? <Notice>{m.categories_empty()}</Notice> : (
          <div className="grid max-h-56 gap-2 overflow-y-auto rounded-lg border border-border p-3
            sm:grid-cols-2">
            {(categories.data ?? []).map((c) => (
              <Checkbox key={c.id} checked={picked.includes(c.id)} label={c.name}
                onChange={(on) => setPicked(on ? [...picked, c.id]
                  : picked.filter((x) => x !== c.id))} />
            ))}
          </div>
        )}
      </FieldGroup>
      <Checkbox checked={playbooks} onChange={setPlaybooks} label={m.copy_playbooks()} />
    </FormModal>
  )
}

/** Superadmin: copy this project's knowledge and playbook choices into another project. */
export function CopyProjectButton({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <Copy />{m.copy_title()}
      </Button>
      {open ? <CopyDialog projectId={projectId} onClose={() => setOpen(false)} /> : null}
    </>
  )
}
