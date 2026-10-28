import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FolderTree, Network, Table2, Trash2, Upload } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { Field } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { ViewToggle } from '../../../components/ui/ViewToggle.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { trustText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  categoryChoicesQuery, documentsQuery, removeDocument, setTrust, TRUST_VALUES, type Trust,
} from '../api.ts'
import { DocumentPreview } from './DocumentPreview.tsx'
import { KnowledgeNetwork } from './KnowledgeNetwork.tsx'
import { UploadDialog } from './UploadDialog.tsx'

type Row = { id: string, title: string, trust: Trust, current_version: number,
  updated_at: string }
const TRUST_TONE = { verified: 'success', claimed: 'warning', disputed: 'destructive',
  unrated: 'default' } as const

function documentColumns(act: { open: (id: string) => void,
  remove: (doc: Row) => void, trust: (doc: Row, t: Trust) => void,
  dateTime: (value: string) => string }): Column<Row>[] {
  return [
    { accessorKey: 'title', header: () => m.col_title(), cell: ({ row }) => (
      <button type="button" className="text-left font-medium text-primary hover:underline"
        onClick={() => act.open(row.original.id)}>{row.original.title}</button>
    ) },
    { accessorKey: 'trust', header: () => m.col_trust(), cell: ({ row }) => (
      <span className="flex items-center gap-2">
        <Badge tone={TRUST_TONE[row.original.trust]}>{trustText(row.original.trust)}</Badge>
        <Select aria-label={m.col_trust()} className="h-8 w-32" value={row.original.trust}
          onChange={(v) => act.trust(row.original, v as Trust)}
          options={TRUST_VALUES.map((t) => ({ value: t, label: trustText(t) }))} />
      </span>
    ) },
    { accessorKey: 'current_version', header: () => m.col_version(), cell: ({ row }) => (
      <Badge tone="outline">{m.docs_version({ n: String(row.original.current_version) })}</Badge>
    ) },
    { accessorKey: 'updated_at', header: () => m.col_updated(),
      cell: ({ row }) => act.dateTime(row.original.updated_at) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <Button variant="ghost" size="sm" className="text-destructive"
        onClick={() => act.remove(row.original)}><Trash2 />{m.action_remove()}</Button>
    ) },
  ]
}

/** The project's documents: the knowledge network by default, a table on request. */
/** `newCategory`: the page's "new category" control, offered while there is none. */
export function DocumentsPanel({ projectId, initialDocument, newCategory }: {
  projectId: string, initialDocument?: string, newCategory?: ReactNode }) {
  const categories = useQuery(categoryChoicesQuery(projectId))
  const [view, setView] = useState<'network' | 'table'>(initialDocument ? 'table' : 'network')
  const [picked, setPicked] = useState('')
  const categoryId = picked || categories.data?.[0]?.id || ''
  const documents = useQuery(documentsQuery(categoryId))
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const { run } = useAction()
  const [open, setOpen] = useState(initialDocument ?? '')
  const [uploading, setUploading] = useState(false)
  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: documentsQuery(categoryId).queryKey }),
    queryClient.invalidateQueries({ queryKey: ['knowledge', 'graph', projectId] }),
  ])
  const remove = async (doc: Row) => {
    const ok = await confirm({ title: m.docs_remove_title({ title: doc.title }),
      description: m.docs_remove_text(), confirmLabel: m.action_remove(), tone: 'destructive' })
    if (!ok) return
    await run(async () => { await removeDocument(doc.id); await refresh() },
      m.docs_removed())
  }
  const columns = documentColumns({
    open: setOpen, remove: (doc) => void remove(doc), dateTime,
    trust: (doc, t) => void run(async () => { await setTrust(doc.id, t); await refresh() },
      m.docs_trust_saved()),
  })
  if (categories.error) return <Notice tone="error">{errorText(categories.error)}</Notice>
  if (categories.data?.length === 0) {
    return (
      <EmptyState icon={<FolderTree className="size-5" />} text={m.cat_create_first()}
        action={newCategory} />
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <ViewToggle value={view} onChange={setView} options={[
          { value: 'network', label: m.view_network(), icon: <Network /> },
          { value: 'table', label: m.view_table(), icon: <Table2 /> },
        ]} />
        <Button className="ml-auto" onClick={() => setUploading(true)}>
          <Upload />{m.docs_upload()}
        </Button>
      </div>
      {view === 'network' ? <KnowledgeNetwork projectId={projectId} onOpen={setOpen} /> : (
        <>
          <Field label={m.docs_category()} className="max-w-xs">
            <Select value={categoryId} onChange={setPicked}
              options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          </Field>
          {documents.error ? <Notice tone="error">{errorText(documents.error)}</Notice> : null}
          <DataTable data={documents.data ?? []} columns={columns} empty={m.docs_empty()}
            loading={documents.isPending} />
        </>
      )}
      {open ? <DocumentPreview documentId={open} onClose={() => setOpen('')} /> : null}
      <UploadDialog open={uploading} onOpenChange={setUploading}
        categories={categories.data ?? []} defaultCategory={categoryId}
        onDone={() => void refresh()} />
    </div>
  )
}
