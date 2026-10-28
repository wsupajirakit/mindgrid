import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { roleText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import {
  type GroupRole, type ProjectRole, projectGroupsQuery, removeGroupRole, ROLES, setGroupRole,
} from '../api.ts'

export type GroupChoice = { id: string, name: string }

function AddGroupDialog({ projectId, choices, open, onOpenChange, onDone }: {
  projectId: string, choices: GroupChoice[], open: boolean,
  onOpenChange: (open: boolean) => void, onDone: () => Promise<void> }) {
  const { busy, run } = useAction()
  const [group, setGroup] = useState('')
  const [role, setRole] = useState<ProjectRole>('viewer')
  const save = async () => {
    const ok = await run(async () => { await setGroupRole(projectId, group, role); await onDone() },
      m.mem_group_added())
    if (ok) { setGroup(''); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.mem_group_add()}
      description={m.mem_group_hint()} submitLabel={m.action_add()} busy={busy}
      disabled={!group} onSubmit={save}>
      <Field label={m.nav_groups()}>
        <Select value={group} onChange={setGroup} placeholder="—"
          options={choices.map((g) => ({ value: g.id, label: g.name }))} />
      </Field>
      <Field label={m.col_role()}>
        <Select value={role} onChange={(v) => setRole(v as ProjectRole)}
          options={ROLES.map((r) => ({ value: r, label: roleText(r) }))} />
      </Field>
    </FormModal>
  )
}

/** The groups that have a role here: every member of a group gets its role. */
export function GroupRolesCard({ projectId, groups, onChanged }: { projectId: string,
  groups: GroupChoice[], onChanged: () => Promise<void> }) {
  const assigned = useQuery(projectGroupsQuery(projectId))
  const queryClient = useQueryClient()
  const { run } = useAction()
  const [adding, setAdding] = useState(false)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: projectGroupsQuery(projectId).queryKey })
    await onChanged()
  }
  const remove = async (g: GroupRole) => {
    const ok = await confirm({ title: m.mem_group_remove_title({ name: g.name }),
      description: m.mem_group_remove_text(), confirmLabel: m.action_remove(),
      tone: 'destructive' })
    if (ok) await run(async () => { await removeGroupRole(projectId, g.group_id); await refresh() },
      m.mem_group_removed())
  }
  const taken = new Set((assigned.data ?? []).map((g) => g.group_id))
  const columns: Column<GroupRole>[] = [
    { accessorKey: 'name', header: () => m.nav_groups(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <UsersRound className="size-4 text-primary" />{row.original.name}
      </span>
    ) },
    { accessorKey: 'role', header: () => m.col_role(), cell: ({ row }) => (
      <Select aria-label={m.col_role()} className="h-8 w-36" value={row.original.role}
        onChange={(v) => void run(async () => {
          await setGroupRole(projectId, row.original.group_id, v as ProjectRole)
          await refresh()
        }, m.mem_role_changed())}
        options={ROLES.map((r) => ({ value: r, label: roleText(r) }))} />
    ) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end">
        <Button variant="ghost" size="icon-sm" className="text-destructive"
          aria-label={m.action_remove()} onClick={() => void remove(row.original)}>
          <Trash2 />
        </Button>
      </span>
    ) },
  ]
  return (
    <Card title={m.mem_groups_title()} description={m.mem_group_hint()} actions={(
      <Button size="sm" onClick={() => setAdding(true)}><Plus />{m.mem_group_add()}</Button>
    )}>
      <DataTable data={assigned.data ?? []} columns={columns} empty={m.mem_groups_empty()}
        loading={assigned.isPending} searchable={false} />
      <AddGroupDialog projectId={projectId} open={adding} onOpenChange={setAdding}
        choices={groups.filter((g) => !taken.has(g.id))} onDone={refresh} />
    </Card>
  )
}
