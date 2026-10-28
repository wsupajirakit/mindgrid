import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { CopyField } from '../../../components/ui/CopyField.tsx'
import { FormModal, Modal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, FieldGroup, Input } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { type Scope, subscribe, subscriptionsQuery, typesQuery } from '../api.ts'

/** A new receiver: name, https URL and the event types it wants; `onSecret` gets its key. */
export function ReceiverDialog({ scope, open, onOpenChange, onSecret }: { scope: Scope,
  open: boolean, onOpenChange: (open: boolean) => void, onSecret: (s: string) => void }) {
  const types = useQuery(typesQuery)
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [picked, setPicked] = useState<string[]>(['*'])
  const toggle = (t: string) => setPicked(picked.includes(t) ? picked.filter((x) => x !== t)
    : t === '*' ? ['*'] : [...picked.filter((x) => x !== '*'), t])
  const save = async () => {
    const ok = await run(async () => {
      const made = await subscribe(scope, name, url, picked.length ? picked : ['*'])
      onSecret(made.secret)
      await queryClient.invalidateQueries({ queryKey: subscriptionsQuery(scope).queryKey })
    }, m.ev_added())
    if (ok) { setName(''); setUrl(''); setPicked(['*']); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} size="lg" title={m.ev_new()}
      description={m.ev_intro()} submitLabel={m.action_add()} busy={busy}
      disabled={!name || !url} onSubmit={save}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={m.col_name()}>
          <Input value={name} autoFocus onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={m.ev_url()}>
          <Input type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
        </Field>
      </div>
      <FieldGroup label={m.ev_types()}>
        <div className="grid gap-2 rounded-lg border border-border p-3 sm:grid-cols-2">
          {['*', ...(types.data ?? []).map((t) => String(t.type))].map((t) => (
            <Checkbox key={t} checked={picked.includes(t)} onChange={() => toggle(t)}
              label={t === '*' ? m.ev_all_types() : <code className="text-xs">{t}</code>} />
          ))}
        </div>
      </FieldGroup>
    </FormModal>
  )
}

/** The signing secret of a new receiver, shown once. */
export function SecretDialog({ secret, onClose }: { secret: string, onClose: () => void }) {
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} title={m.ev_secret_title()}>
      <div className="flex flex-col gap-3">
        <Notice tone="warn">{m.ev_secret_note()}</Notice>
        <CopyField value={secret} rows={2} label={m.ev_secret_title()} />
      </div>
    </Modal>
  )
}
