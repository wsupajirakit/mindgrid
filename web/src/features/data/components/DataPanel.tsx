import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Upload } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { datasetsQuery } from '../api.ts'
import { DatasetDetail, UploadDatasetDialog } from './DatasetDialogs.tsx'

type Dataset = { id: string, name: string, title: string, source: string,
  current_version: number, updated_at: string }

/** Datasets of a project: versions (one per change) and a preview of the newest one. */
export function DataPanel({ projectId, initialDataset }: { projectId: string,
  initialDataset?: string }) {
  const datasets = useQuery(datasetsQuery(projectId))
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const [open, setOpen] = useState(initialDataset ?? '')
  const [uploading, setUploading] = useState(false)
  const columns: Column<Dataset>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <Database className="size-4 text-primary" />{row.original.name}
      </span>
    ) },
    { accessorKey: 'source', header: () => m.col_description(),
      cell: ({ row }) => <Badge tone="outline">{row.original.source}</Badge> },
    { accessorKey: 'current_version', header: () => m.col_version(),
      cell: ({ row }) => <Badge>{`v${String(row.original.current_version)}`}</Badge> },
    { accessorKey: 'updated_at', header: () => m.col_updated(),
      cell: ({ row }) => dateTime(row.original.updated_at) },
  ]
  return (
    <Card title={m.tab_data()} description={m.data_intro()} actions={(
      <Button size="sm" onClick={() => setUploading(true)}><Upload />{m.data_new()}</Button>
    )}>
      {datasets.error ? <Notice tone="error">{errorText(datasets.error)}</Notice> : null}
      <DataTable data={datasets.data ?? []} columns={columns} empty={m.data_empty()}
        loading={datasets.isPending} onRowClick={(d) => setOpen(d.name)} />
      {open ? <DatasetDetail projectId={projectId} name={open} onClose={() => setOpen('')} />
        : null}
      <UploadDatasetDialog projectId={projectId} open={uploading} onOpenChange={setUploading}
        onDone={() => void queryClient.invalidateQueries({
          queryKey: datasetsQuery(projectId).queryKey })} />
    </Card>
  )
}
