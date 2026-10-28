import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { FormModal, Modal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  DATASET_NAME, type Format, FORMATS, rowsQuery, uploadDataset, versionsQuery,
} from '../api.ts'

const MAX_COLUMNS = 12

export function UploadDatasetDialog({ projectId, open, onOpenChange, onDone }: {
  projectId: string, open: boolean, onOpenChange: (open: boolean) => void,
  onDone: () => void }) {
  const { busy, run } = useAction()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [format, setFormat] = useState<Format>('csv')
  const [path, setPath] = useState('')
  const send = async () => {
    if (!file) return
    const ok = await run(() => uploadDataset(projectId, name, file, format, path),
      m.data_uploaded())
    if (ok) { setName(''); setFile(null); setPath(''); onDone(); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.data_new()}
      submitLabel={m.docs_upload()} busy={busy} disabled={!file || !DATASET_NAME.test(name)}
      onSubmit={send}>
      <Field label={m.data_name()} hint={m.data_name_hint()}>
        <Input value={name} autoFocus onChange={(e) => setName(e.target.value.toLowerCase())} />
      </Field>
      <Field label={m.data_file()}>
        <Input type="file" accept=".csv,.json,.ndjson,.jsonl" className="h-auto py-1.5"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={m.data_format()}>
          <Select value={format} onChange={(v) => setFormat(v as Format)}
            options={FORMATS.map((f) => ({ value: f, label: f.toUpperCase() }))} />
        </Field>
        <Field label={m.data_records_path()}>
          <Input value={path} disabled={format !== 'json'}
            onChange={(e) => setPath(e.target.value)} />
        </Field>
      </div>
    </FormModal>
  )
}

/** Versions of a dataset and the first rows of the newest one. */
export function DatasetDetail({ projectId, name, onClose }: { projectId: string, name: string,
  onClose: () => void }) {
  const versions = useQuery(versionsQuery(projectId, name))
  const rows = useQuery(rowsQuery(projectId, name))
  const { dateTime } = useFormat()
  const columns = (rows.data?.columns ?? []).slice(0, MAX_COLUMNS)
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="xl"
      title={m.data_detail({ name })}>
      <div className="flex flex-col gap-4 text-sm">
        {rows.error ? <Notice tone="error">{errorText(rows.error)}</Notice> : null}
        <h3 className="font-semibold">{m.data_versions()}</h3>
        <ul className="flex flex-wrap gap-2">
          {(versions.data ?? []).map((v) => (
            <li key={String(v.version)}>
              <Badge tone="outline">{`v${String(v.version)} · ${m.data_rows({
                n: String(v.rows) })} · ${dateTime(String(v.created_at))}`}</Badge>
            </li>
          ))}
        </ul>
        <h3 className="font-semibold">{m.data_preview()}</h3>
        {rows.isPending ? <Skeleton className="h-40" /> : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-xs">
              <thead className="bg-muted/60 text-muted-foreground">
                <tr>{columns.map((c) => (
                  <th key={c} className="px-3 py-2 text-left font-medium">{c}</th>
                ))}</tr>
              </thead>
              <tbody>
                {(rows.data?.items ?? []).map((r, i) => (
                  <tr key={i} className="border-t border-border">
                    {columns.map((c) => (
                      <td key={c} className="px-3 py-1.5">{String(r[c] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Modal>
  )
}
