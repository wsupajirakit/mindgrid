import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Trash2, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import type { PersonInfo } from '../../../components/ui/Person.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { deleteGroup, type Group, groupsQuery } from '../api.ts'
import { GroupDialog, GroupMembersDialog } from './GroupDialogs.tsx'

type Open = { kind: 'edit', group: Group | null } | { kind: 'members', group: Group } | null

/** Groups of people (superadmin): projects and categories give rights to a whole group;
 * `people` (composed by the page from the users list) are who may be added. */
export function GroupsPage({ people }: { people: (PersonInfo & { id: string })[] }) {
  useDocumentTitle(m.nav_groups())
  const groups = useQuery(groupsQuery)
  const queryClient = useQueryClient()
  const { run } = useAction()
  const [open, setOpen] = useState<Open>(null)
  const remove = async (g: Group) => {
    const ok = await confirm({ title: m.groups_delete_title({ name: g.name }),
      description: m.groups_delete_text(), confirmLabel: m.action_remove(), tone: 'destructive' })
    if (ok) await run(async () => {
      await deleteGroup(g.id)
      await queryClient.invalidateQueries({ queryKey: ['groups'] })
    }, m.groups_deleted())
  }
  const columns: Column<Group>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2 font-medium">
          <UsersRound className="size-4 text-primary" />{row.original.name}
        </span>
        {row.original.description ? (
          <span className="line-clamp-1 text-xs text-muted-foreground">
            {row.original.description}
          </span>
        ) : null}
      </span>
    ) },
    { accessorKey: 'members', header: () => m.groups_members(), cell: ({ row }) => (
      <Badge tone="outline">{m.groups_member_count({ n: String(row.original.members) })}</Badge>
    ) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end gap-1">
        <Button variant="ghost" size="sm"
          onClick={() => setOpen({ kind: 'members', group: row.original })}>
          <UsersRound />{m.groups_members()}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label={m.ui_edit()}
          onClick={() => setOpen({ kind: 'edit', group: row.original })}><Pencil /></Button>
        <Button variant="ghost" size="icon-sm" aria-label={m.action_remove()}
          className="text-destructive" onClick={() => void remove(row.original)}>
          <Trash2 />
        </Button>
      </span>
    ) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<UsersRound />} title={m.nav_groups()} description={m.groups_intro()}
        actions={(
          <Button onClick={() => setOpen({ kind: 'edit', group: null })}>
            <Plus />{m.groups_new()}
          </Button>
        )} />
      {groups.error ? <Notice tone="error">{errorText(groups.error)}</Notice> : null}
      <Card>
        <DataTable data={groups.data ?? []} columns={columns} empty={m.groups_empty()}
          loading={groups.isPending} />
      </Card>
      {open?.kind === 'edit' ? <GroupDialog group={open.group} onClose={() => setOpen(null)} />
        : null}
      {open?.kind === 'members' ? (
        <GroupMembersDialog group={open.group} people={people} onClose={() => setOpen(null)} />
      ) : null}
    </div>
  )
}
