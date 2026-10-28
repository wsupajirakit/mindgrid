import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { type ConnectorRow, DATASET_NAME, saveConnector, templatesQuery } from '../api.ts'

/** Create a connector (from a template) or edit one: name, schedule, JSON spec. */
export function ConnectorDialog({ projectId, connector, onClose, onDone }: {
  projectId: string, connector: ConnectorRow | null, onClose: () => void,
  onDone: () => void }) {
  const templates = useQuery(templatesQuery)
  const { busy, run } = useAction()
  const [name, setName] = useState(connector?.name ?? '')
  const [spec, setSpec] = useState(connector ? JSON.stringify(connector.spec, null, 2) : '')
  const [every, setEvery] = useState(connector?.every_minutes == null ? ''
    : String(connector.every_minutes))
  const pick = (id: string) => {
    const t = templates.data?.find((x) => x.id === id)
    if (!t) return
    setName(t.id); setSpec(JSON.stringify(t.spec, null, 2))
    setEvery(t.every_minutes === null ? '' : String(t.every_minutes))
  }
  const save = async () => {
    const ok = await run(() => saveConnector(projectId, name, JSON.parse(spec),
      every === '' ? null : Number(every)), m.conn_saved())
    if (ok) { onDone(); onClose() }
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="lg"
      title={connector ? m.conn_edit({ name: connector.name }) : m.conn_new()}
      description={m.conn_intro()} submitLabel={m.action_save()} busy={busy}
      disabled={!DATASET_NAME.test(name) || !spec || !/^\d*$/.test(every)} onSubmit={save}>
      {connector ? null : (
        <Field label={m.conn_template()}>
          <Select onChange={pick} placeholder="—"
            options={(templates.data ?? []).map((t) => ({ value: t.id, label: t.title }))} />
        </Field>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={m.conn_name()}>
          <Input value={name} disabled={connector !== null}
            onChange={(e) => setName(e.target.value.toLowerCase())} />
        </Field>
        <Field label={m.conn_every()}>
          <Input inputMode="numeric" value={every} onChange={(e) => setEvery(e.target.value)} />
        </Field>
      </div>
      <Field label={m.conn_spec()}>
        <Textarea rows={12} className="font-mono text-xs" value={spec}
          onChange={(e) => setSpec(e.target.value)} />
      </Field>
      <Notice>{m.conn_secret_hint()}</Notice>
    </FormModal>
  )
}
