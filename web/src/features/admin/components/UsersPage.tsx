import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus, UserCheck, Users, UsersRound, UserX } from 'lucide-react'
import { useState } from 'react'
import { Avatar } from '../../../components/ui/Avatar.tsx'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { setStatus, usersQuery } from '../api.ts'
import {
  type GroupChoice, NewUserDialog, ResetDialog, UserGroupsDialog, type UserRow,
} from './UserDialogs.tsx'

type Row = UserRow
type Handlers = { dateTime: (at: string) => string, onGroups: (u: Row) => void,
  onReset: (u: Row) => void, onToggle: (u: Row) => void }

function userColumns({ dateTime, onGroups, onReset, onToggle }: Handlers): Column<Row>[] {
return [
  { id: 'name', accessorFn: (u) => `${u.display_name} ${u.email}`, header: () => m.col_name(),
    cell: ({ row }) => (
      <span className="flex items-center gap-3">
        <Avatar name={row.original.display_name} avatar={row.original.avatar} />
        <span className="min-w-0">
          <span className="block truncate font-medium">{row.original.display_name}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {row.original.email}
          </span>
        </span>
      </span>
    ) },
  { accessorKey: 'system_role', header: () => m.col_role(), cell: ({ row }) =>
    row.original.system_role === 'superadmin'
      ? <Badge tone="primary">{m.role_superadmin()}</Badge> : <Badge>{m.role_user()}</Badge> },
  { accessorKey: 'status', header: () => m.col_status(), cell: ({ row }) =>
    row.original.status === 'active' ? <Badge tone="success">{m.status_active()}</Badge>
      : <Badge tone="destructive">{m.status_disabled()}</Badge> },
  { id: 'groups', accessorFn: (u) => (u.groups ?? []).map((g) => g.name).join(' '),
    header: () => m.nav_groups(), cell: ({ row }) => (
      <span className="flex flex-wrap gap-1">
        {(row.original.groups ?? []).map((g) => (
          <Badge key={g.id} tone="outline">{g.name}</Badge>
        ))}
      </span>
    ) },
  { accessorKey: 'last_login_at', header: () => m.users_last_login(), cell: ({ row }) =>
    row.original.last_login_at ? dateTime(row.original.last_login_at) : m.users_never() },
  { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
    <span className="flex justify-end gap-1">
      <Button variant="ghost" size="sm" onClick={() => onGroups(row.original)}>
        <UsersRound />{m.nav_groups()}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onReset(row.original)}>
        <KeyRound />{m.users_reset()}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onToggle(row.original)}>
        {row.original.status === 'active' ? <UserX /> : <UserCheck />}
        {row.original.status === 'active' ? m.action_disable() : m.action_enable()}
      </Button>
    </span>
  ) },
]
}

/** `groups`: the groups a person may join (the page composes them from the groups list). */
export function UsersPage({ groups }: { groups: GroupChoice[] }) {
  useDocumentTitle(m.nav_users())
  const users = useQuery(usersQuery)
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const { run } = useAction()
  const [creating, setCreating] = useState(false)
  const [resetting, setResetting] = useState<Row | null>(null)
  const [grouping, setGrouping] = useState<Row | null>(null)
  const toggle = async (user: Row) => {
    const active = user.status === 'active'
    const ok = await confirm({
      title: active ? m.users_disable_title({ name: user.display_name })
        : m.users_enable_title({ name: user.display_name }),
      description: active ? m.users_disable_text() : m.users_enable_text(),
      confirmLabel: active ? m.action_disable() : m.action_enable(),
      tone: active ? 'destructive' : 'default',
    })
    if (!ok) return
    await run(async () => {
      await setStatus(user.id, active ? 'disabled' : 'active')
      await queryClient.invalidateQueries({ queryKey: usersQuery.queryKey })
    }, active ? m.users_disabled() : m.users_enabled())
  }
  const columns = userColumns({ dateTime, onGroups: setGrouping, onReset: setResetting,
    onToggle: (u) => void toggle(u) })
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<Users />} title={m.users_title()} description={m.users_intro()}
        actions={<Button onClick={() => setCreating(true)}><Plus />{m.users_new()}</Button>} />
      {users.error ? <Notice tone="error">{errorText(users.error)}</Notice> : null}
      <Card>
        <DataTable data={users.data ?? []} columns={columns} empty={m.users_empty()}
          loading={users.isPending} />
      </Card>
      <NewUserDialog open={creating} onOpenChange={setCreating} groups={groups} />
      {grouping ? <UserGroupsDialog user={grouping} groups={groups}
        onClose={() => setGrouping(null)} /> : null}
      {resetting ? <ResetDialog user={resetting} onClose={() => setResetting(null)} /> : null}
    </div>
  )
}
