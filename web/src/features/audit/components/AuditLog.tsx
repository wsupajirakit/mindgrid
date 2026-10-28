import { useInfiniteQuery } from '@tanstack/react-query'
import { Button } from '../../../components/ui/Button.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Person } from '../../../components/ui/Person.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type AuditEvent, auditQuery } from '../api.ts'

type Row = AuditEvent

/** The target in words: a user target and a key's owner by name and email. */
function Target({ row }: { row: Row }) {
  const user = row.target_type === 'user' ? row.people?.[row.target_id] : undefined
  const owner = typeof row.details.owner === 'string' ? row.people?.[row.details.owner] : undefined
  if (user) return <Person person={user} fallback={row.target_id} />
  return (
    <span className="flex flex-col gap-1 text-xs text-muted-foreground">
      <span>{`${row.target_type} ${row.target_id}`.trim()}</span>
      {owner ? <Person person={owner} fallback="" /> : null}
    </span>
  )
}

/** The audit log (one project's, or everything the caller may see); older pages on demand. */
export function AuditLog({ projectId }: { projectId?: string }) {
  const log = useInfiniteQuery(auditQuery(projectId))
  const { dateTime } = useFormat()
  const columns: Column<Row>[] = [
    { accessorKey: 'at', header: () => m.col_when(),
      cell: ({ row }) => <span className="whitespace-nowrap">{dateTime(row.original.at)}</span> },
    { accessorKey: 'action', header: () => m.col_action(), cell: ({ row }) => (
      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{row.original.action}</code>
    ) },
    { id: 'target', header: () => m.col_target(),
      accessorFn: (r) => [r.target_type, r.target_id,
        ...Object.values(r.people ?? {}).flatMap((p) => [p.name, p.email])].join(' '),
      cell: ({ row }) => <Target row={row.original} /> },
    { id: 'actor', header: () => m.col_actor(),
      accessorFn: (r) => r.actor ? `${r.actor.name} ${r.actor.email}` : '',
      cell: ({ row }) => (
        <Person person={row.original.actor}
          fallback={row.original.actor_user_id ? m.actor_unknown() : m.actor_system()} />
      ) },
  ]
  const rows = log.data?.pages.flat() ?? []
  return (
    <div className="flex flex-col gap-3">
      {log.error ? <Notice tone="error">{errorText(log.error)}</Notice> : null}
      <DataTable data={rows} columns={columns} empty={m.audit_empty()} loading={log.isPending}
        pageSize={20} toolbar={log.hasNextPage ? (
          <Button variant="outline" onClick={() => void log.fetchNextPage()}
            disabled={log.isFetchingNextPage}>{m.action_more()}</Button>
        ) : null} />
    </div>
  )
}
