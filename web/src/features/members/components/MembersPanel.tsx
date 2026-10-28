import { useQuery, useQueryClient } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { ALL, Select } from '../../../components/ui/Select.tsx'
import { Person as PersonLabel } from '../../../components/ui/Person.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { roleText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import {
  inviteMember, membersQuery, peopleQuery, type Person, type ProjectRole, removeMember, ROLES,
  setRole,
} from '../api.ts'
import { type GroupChoice, GroupRolesCard } from './GroupRolesCard.tsx'

const OWN = 'own'  // select value prefix; ALL = use the groups' role

function Source({ p }: { p: Person }) {
  if (p.owner) return <Badge tone="primary">{m.mem_owner()}</Badge>
  return (
    <span className="flex flex-wrap gap-1">
      {p.own_role ? <Badge tone="success">{m.mem_own_role()}</Badge> : null}
      {p.via.map((g) => (
        <Badge key={g.group_id} tone="outline">{`${g.name} · ${roleText(g.role)}`}</Badge>
      ))}
    </span>
  )
}

function InviteDialog({ projectId, open, onOpenChange, onDone }: { projectId: string,
  open: boolean, onOpenChange: (open: boolean) => void, onDone: () => Promise<void> }) {
  const { busy, run } = useAction()
  const [email, setEmail] = useState('')
  const [role, setNewRole] = useState<ProjectRole>('viewer')
  const invite = async () => {
    const ok = await run(async () => { await inviteMember(projectId, email, role); await onDone() },
      m.mem_invited())
    if (ok) { setEmail(''); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.mem_invite_title()}
      submitLabel={m.members_invite()} busy={busy} disabled={!email} onSubmit={invite}>
      <Field label={m.field_email()} hint={m.mem_invite_hint()}>
        <Input type="email" value={email} autoFocus onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label={m.col_role()}>
        <Select value={role} onChange={(v) => setNewRole(v as ProjectRole)}
          options={ROLES.map((r) => ({ value: r, label: roleText(r) }))} />
      </Field>
    </FormModal>
  )
}

/** Who can work here: groups (everyone in them) and people (their own role wins). */
export function MembersPanel({ projectId, groups }: { projectId: string,
  groups: GroupChoice[] }) {
  const people = useQuery(peopleQuery(projectId))
  const queryClient = useQueryClient()
  const { run } = useAction()
  const [inviting, setInviting] = useState(false)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: peopleQuery(projectId).queryKey })
    await queryClient.invalidateQueries({ queryKey: membersQuery(projectId).queryKey })
  }
  const change = async (p: Person, value: string) => {
    if (value === ALL) {
      const ok = await confirm({ title: m.mem_drop_own_title({ name: p.name }),
        description: p.via.length ? m.mem_drop_own_text() : m.mem_remove_text(),
        confirmLabel: m.action_remove(), tone: 'destructive' })
      if (ok) await run(async () => { await removeMember(projectId, p.user_id); await refresh() },
        m.mem_removed())
      return
    }
    await run(async () => {
      await setRole(projectId, p.user_id, value.slice(OWN.length + 1) as ProjectRole)
      await refresh()
    }, m.mem_role_changed())
  }
  const columns: Column<Person>[] = [
    { id: 'person', accessorFn: (p) => `${p.name} ${p.email}`, header: () => m.col_user(),
      cell: ({ row }) => <PersonLabel person={row.original} fallback="" /> },
    { id: 'role', accessorFn: (p) => p.role ?? '', header: () => m.mem_role_now(),
      cell: ({ row }) => row.original.owner ? <Badge tone="primary">{m.mem_owner()}</Badge>
        : <Badge>{row.original.role ? roleText(row.original.role) : '—'}</Badge> },
    { id: 'source', header: () => m.mem_from(), enableSorting: false,
      cell: ({ row }) => <Source p={row.original} /> },
    { id: 'own', header: () => m.mem_own_role(), enableSorting: false, cell: ({ row }) =>
      row.original.owner ? null : (
        <Select aria-label={m.mem_own_role()} className="h-8 w-44"
          value={row.original.own_role ? `${OWN}:${row.original.own_role}` : ALL}
          onChange={(v) => void change(row.original, v)} options={[
            { value: ALL, label: row.original.via.length ? m.mem_use_groups() : '—' },
            ...ROLES.map((r) => ({ value: `${OWN}:${r}`, label: roleText(r) })),
          ]} />
      ) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <GroupRolesCard projectId={projectId} groups={groups} onChanged={refresh} />
      <Card title={m.mem_people_title()} description={m.mem_people_hint()} actions={(
        <Button size="sm" onClick={() => setInviting(true)}>
          <UserPlus />{m.members_invite()}
        </Button>
      )}>
        <DataTable data={people.data ?? []} columns={columns} empty={m.members_empty()}
          loading={people.isPending} />
      </Card>
      <InviteDialog projectId={projectId} open={inviting} onOpenChange={setInviting}
        onDone={refresh} />
    </div>
  )
}
