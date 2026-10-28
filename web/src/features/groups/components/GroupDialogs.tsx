import { useQuery, useQueryClient } from '@tanstack/react-query'
import { UserMinus, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { FormModal, Modal } from '../../../components/ui/Dialog.tsx'
import { Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Person, type PersonInfo } from '../../../components/ui/Person.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import {
  addGroupMember, createGroup, type Group, type GroupMember, groupMembersQuery, groupsQuery,
  removeGroupMember, updateGroup,
} from '../api.ts'

/** New group, or edit one (name and description). */
export function GroupDialog({ group, onClose }: { group: Group | null, onClose: () => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState({ name: group?.name ?? '',
    description: group?.description ?? '' })
  const save = async () => {
    const ok = await run(async () => {
      if (group) await updateGroup(group.id, form.name, form.description)
      else await createGroup(form.name, form.description)
      await queryClient.invalidateQueries({ queryKey: groupsQuery.queryKey })
    }, group ? m.groups_saved() : m.groups_created())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }}
      title={group ? m.groups_edit({ name: group.name }) : m.groups_new()}
      description={m.groups_intro()} submitLabel={group ? m.action_save() : m.action_create()}
      busy={busy} disabled={!form.name.trim()} onSubmit={save}>
      <Field label={m.col_name()}>
        <Input value={form.name} autoFocus maxLength={120}
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label={m.col_description()}>
        <Textarea rows={3} value={form.description} maxLength={2000}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </Field>
    </FormModal>
  )
}

/** Who is in a group: add anyone from `people`, remove with a confirm. */
export function GroupMembersDialog({ group, people, onClose }: { group: Group,
  people: (PersonInfo & { id: string })[], onClose: () => void }) {
  const members = useQuery(groupMembersQuery(group.id))
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [picked, setPicked] = useState('')
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['groups'] })
    await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
  }
  const inGroup = new Set((members.data ?? []).map((u) => u.user_id))
  const add = async () => {
    if (await run(async () => { await addGroupMember(group.id, picked); await refresh() },
      m.groups_member_added())) setPicked('')
  }
  const remove = async (u: GroupMember) => {
    const ok = await confirm({ title: m.groups_member_remove_title({ name: u.name }),
      description: m.groups_member_remove_text({ group: group.name }),
      confirmLabel: m.action_remove(), tone: 'destructive' })
    if (ok) await run(async () => { await removeGroupMember(group.id, u.user_id); await refresh() },
      m.groups_member_removed())
  }
  const columns: Column<GroupMember>[] = [
    { id: 'person', accessorFn: (u) => `${u.name} ${u.email}`, header: () => m.col_name(),
      cell: ({ row }) => <Person person={row.original} fallback="" /> },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end">
        <Button variant="ghost" size="sm" className="text-destructive"
          onClick={() => void remove(row.original)}><UserMinus />{m.action_remove()}</Button>
      </span>
    ) },
  ]
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="lg"
      title={m.groups_members_of({ name: group.name })} description={m.groups_members_hint()}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-2">
          <Field label={m.groups_add_person()} className="min-w-0 flex-1">
            <Select value={picked} onChange={setPicked} placeholder="—"
              options={people.filter((p) => !inGroup.has(p.id))
                .map((p) => ({ value: p.id, label: `${p.name} · ${p.email}` }))} />
          </Field>
          <Button disabled={!picked || busy} onClick={() => void add()}>
            <UserPlus />{m.action_add()}
          </Button>
        </div>
        <DataTable data={members.data ?? []} columns={columns} empty={m.groups_no_members()}
          loading={members.isPending} />
      </div>
    </Modal>
  )
}
