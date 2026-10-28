import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Assignments, assignmentsQuery, saveAssignments } from '../api.ts'

function Body({ data, superadmin, onSaved, onClose, title }: { data: Assignments,
  superadmin: boolean, onSaved: () => void, onClose: () => void, title: string }) {
  const { busy, run } = useAction()
  const [all, setAll] = useState(data.all_projects)
  const [on, setOn] = useState<Record<string, boolean>>(
    Object.fromEntries(data.projects.map((p) => [p.project_id, p.enabled])))
  const managed = data.projects.filter((p) => p.can_manage)
  const save = async () => {
    // Every managed project gets an explicit choice: "every project" keeps them all on.
    const choices = Object.fromEntries(managed.map((p) => [p.project_id,
      superadmin && all ? true : on[p.project_id] === true]))
    const ok = await run(async () => {
      await saveAssignments(data.playbook_id, superadmin ? all : null, choices)
      onSaved()
    }, m.pb_assign_saved())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} title={m.pb_assign_title({ title })}
      submitLabel={m.action_save()} busy={busy} disabled={managed.length === 0} onSubmit={save}>
      {superadmin ? (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <Checkbox checked={all} onChange={setAll} label={m.pb_assign_all()} />
          <p className="pl-6 text-xs text-muted-foreground">{m.pb_assign_all_hint()}</p>
        </div>
      ) : null}
      {managed.length === 0 ? <Notice>{m.pb_assign_none()}</Notice> : (
        <fieldset disabled={superadmin && all} className="flex flex-col gap-2 disabled:opacity-50">
          <legend className="mb-2 text-sm font-medium">{m.pb_assign_selected()}</legend>
          <div className="grid max-h-72 gap-2 overflow-y-auto rounded-lg border border-border p-3
            sm:grid-cols-2">
            {managed.map((p) => (
              <Checkbox key={p.project_id} checked={superadmin && all ? true : on[p.project_id]
                === true} label={p.name}
                onChange={(v) => setOn({ ...on, [p.project_id]: v })} />
            ))}
          </div>
        </fieldset>
      )}
    </FormModal>
  )
}

/** Which projects may run a playbook: every project (superadmin) or the ticked ones. */
export function AssignDialog({ playbookId, title, superadmin, onClose }: { playbookId: string,
  title: string, superadmin: boolean, onClose: () => void }) {
  const query = useQuery(assignmentsQuery(playbookId))
  const queryClient = useQueryClient()
  if (query.error) return <Notice tone="error">{errorText(query.error)}</Notice>
  if (!query.data) return <Skeleton className="h-10" />
  return (
    <Body data={query.data} superadmin={superadmin} title={title} onClose={onClose}
      onSaved={() => void queryClient.invalidateQueries({ queryKey: ['playbooks'] })
        .then(() => queryClient.invalidateQueries({ queryKey: ['projects'] }))} />
  )
}
