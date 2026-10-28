import { useQuery } from '@tanstack/react-query'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { type EventRow, eventsQuery } from '../api.ts'

/** What this project emitted, newest first; each event links to the page it is about. */
export function EventLog({ projectId }: { projectId: string }) {
  const rows = useQuery(eventsQuery(projectId))
  const { dateTime } = useFormat()
  const columns: Column<EventRow>[] = [
    { accessorKey: 'created_at', header: () => m.col_when(),
      cell: ({ row }) => (
        <span className="whitespace-nowrap">{dateTime(row.original.created_at)}</span>) },
    { accessorKey: 'type', header: () => m.ev_type(),
      cell: ({ row }) => <Badge tone="primary">{row.original.type}</Badge> },
    { accessorKey: 'subject', header: () => m.ev_subject(), cell: ({ row }) => {
      const ui = (row.original.data.links as { ui?: string } | undefined)?.ui
      return ui ? <a className="text-primary hover:underline" href={ui}>{row.original.subject}</a>
        : row.original.subject
    } },
  ]
  return (
    <Card title={m.ev_log()}>
      <DataTable data={rows.data ?? []} columns={columns} empty={m.ev_log_empty()}
        loading={rows.isPending} />
    </Card>
  )
}
