import { useQuery } from '@tanstack/react-query'
import { Workflow } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { playbookStatusText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type RunRow, runsQuery } from '../api.ts'
import { RunById, RunStatusBadge } from './RunDetail.tsx'

/** Runs of a project, newest first; refreshes while a run is queued or running. */
export function RunsPanel({ projectId, initialRun }: { projectId: string, initialRun?: string }) {
  const runs = useQuery(runsQuery(projectId))
  const { dateTime } = useFormat()
  const [open, setOpen] = useState(initialRun ?? '')
  const columns: Column<RunRow>[] = [
    { accessorKey: 'playbook_id', header: () => m.pb_playbook(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <Workflow className="size-4 text-primary" />
        {`${row.original.playbook_id} v${String(row.original.playbook_version)}`}
      </span>
    ) },
    { accessorKey: 'playbook_status', header: () => m.pb_version_status(),
      cell: ({ row }) => <Badge>{playbookStatusText(row.original.playbook_status)}</Badge> },
    { accessorKey: 'status', header: () => m.col_status(),
      cell: ({ row }) => <RunStatusBadge status={row.original.status} /> },
    { accessorKey: 'created_at', header: () => m.col_when(),
      cell: ({ row }) => dateTime(row.original.created_at) },
  ]
  const picked = runs.data?.find((r) => r.id === open)
  return (
    <Card title={m.tab_runs()} description={m.runs_intro()}>
      {runs.error ? <Notice tone="error">{errorText(runs.error)}</Notice> : null}
      <DataTable data={runs.data ?? []} columns={columns} empty={m.pb_no_runs()}
        loading={runs.isPending} onRowClick={(r) => setOpen(r.id)} />
      {open ? (
        <Modal open onOpenChange={(o) => { if (!o) setOpen('') }} size="lg"
          title={m.runs_detail({ playbook: picked?.playbook_id ?? '' })}>
          <RunById id={open} />
        </Modal>
      ) : null}
    </Card>
  )
}
