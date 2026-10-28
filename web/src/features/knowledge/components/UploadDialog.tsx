import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { trustText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { TRUST_VALUES, type Trust, uploadDocument } from '../api.ts'

const ACCEPT = '.txt,.md,.markdown,.csv,.pdf,.docx'

export function UploadDialog({ open, onOpenChange, categories, defaultCategory, onDone }: {
  open: boolean, onOpenChange: (open: boolean) => void,
  categories: { id: string, name: string }[], defaultCategory: string, onDone: () => void }) {
  const { busy, run } = useAction()
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [trust, setTrustValue] = useState<Trust>('unrated')
  const [category, setCategory] = useState('')
  const target = category || defaultCategory
  const send = async () => {
    if (!file) return
    const ok = await run(() => uploadDocument(target, file, title, trust), m.docs_uploaded())
    if (ok) { setFile(null); setTitle(''); onDone(); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.docs_upload_title()}
      description={m.docs_upload_hint()} submitLabel={m.docs_upload()} busy={busy}
      disabled={!file || !target} onSubmit={send}>
      <Field label={m.docs_category()}>
        <Select value={target} onChange={setCategory}
          options={categories.map((c) => ({ value: c.id, label: c.name }))} />
      </Field>
      <Field label={m.docs_file()}>
        <Input type="file" accept={ACCEPT} className="h-auto py-1.5"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </Field>
      <Field label={m.docs_title_optional()}>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field label={m.col_trust()}>
        <Select value={trust} onChange={(v) => setTrustValue(v as Trust)}
          options={TRUST_VALUES.map((t) => ({ value: t, label: trustText(t) }))} />
      </Field>
    </FormModal>
  )
}
