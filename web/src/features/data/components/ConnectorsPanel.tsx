import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Cable, Pencil, Plus, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge, type BadgeTone } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type ConnectorRow, connectorsQuery, syncConnector } from '../api.ts'
import { ConnectorDialog } from './ConnectorDialog.tsx'

const TONE: Record<string, BadgeTone> = { ok: 'success', failed: 'destructive',
  running: 'warning', queued: 'warning' }

/** Generic connectors: start from a template, edit the spec, sync on request or schedule. */
export function ConnectorsPanel({ projectId }: { projectId: string }) {
  const list = useQuery(connectorsQuery(projectId))
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const { run } = useAction()
  const [editing, setEditing] = useState<ConnectorRow | 'new' | null>(null)
  const refresh = () => queryClient.invalidateQueries({
    queryKey: connectorsQuery(projectId).queryKey })
  const sync = (c: ConnectorRow) => run(async () => {
    await syncConnector(c.id)
    await refresh()
  }, m.conn_synced())
  const columns: Column<ConnectorRow>[] = [
    { accessorKey: 'name', header: () => m.conn_name(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <Cable className="size-4 text-primary" />{row.original.name}
      </span>
    ) },
    { accessorKey: 'last_status', header: () => m.col_status(), cell: ({ row }) => (
      <span className="flex flex-col gap-1">
        <Badge tone={TONE[row.original.last_status] ?? 'default'}>
          {row.original.last_status}
        </Badge>
        {row.original.last_error ? (
          <span className="line-clamp-2 max-w-xs text-xs text-destructive">
            {row.original.last_error}
          </span>
        ) : null}
      </span>
    ) },
    { accessorKey: 'every_minutes', header: () => m.conn_schedule(), cell: ({ row }) =>
      row.original.every_minutes === null ? m.conn_on_request()
        : m.conn_every_n({ n: String(row.original.every_minutes) }) },
    { accessorKey: 'last_run_at', header: () => m.conn_last(), cell: ({ row }) =>
      row.original.last_run_at ? dateTime(row.original.last_run_at) : m.conn_never() },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end gap-1">
        <Button variant="ghost" size="sm" onClick={() => void sync(row.original)}>
          <RefreshCw />{m.conn_sync()}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label={m.ui_edit()}
          onClick={() => setEditing(row.original)}><Pencil /></Button>
      </span>
    ) },
  ]
  return (
    <Card title={m.tab_connectors()} description={m.conn_intro()} actions={(
      <Button size="sm" onClick={() => setEditing('new')}><Plus />{m.conn_new()}</Button>
    )}>
      {list.error ? <Notice tone="error">{errorText(list.error)}</Notice> : null}
      <DataTable data={list.data ?? []} columns={columns} empty={m.conn_empty()}
        loading={list.isPending} />
      {editing ? (
        <ConnectorDialog projectId={projectId} connector={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)} onDone={() => void refresh()} />
      ) : null}
    </Card>
  )
}
