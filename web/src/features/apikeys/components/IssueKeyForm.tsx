import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, Input } from '../../../components/ui/Field.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { issueKey, type KeyScope, SCOPES } from '../api.ts'

const scopeText: Record<KeyScope, () => string> = {
  read: () => m.scope_read(), run: () => m.scope_run(), edit: () => m.scope_edit(),
}

export type Owner = { id: string, email: string, name: string, avatar?: string }

/** Issue a key in a modal; the private key comes back once and is handed to `onIssued`. */
export function IssueKeyDialog({ owners, open, onOpenChange, onIssued }: { owners: Owner[],
  open: boolean, onOpenChange: (open: boolean) => void,
  onIssued: (keyId: string, privateKey: string) => void }) {
  const { busy, run } = useAction()
  const [owner, setOwner] = useState('')
  const [name, setName] = useState('')
  const [days, setDays] = useState(90)
  const [scopes, setScopes] = useState<KeyScope[]>(['read'])
  const toggle = (scope: KeyScope, on: boolean) => setScopes((now) =>
    on ? [...now.filter((s) => s !== scope), scope] : now.filter((s) => s !== scope))
  const submit = async () => {
    const ok = await run(async () => {
      const issued = await issueKey({ owner_user_id: owner, name, scopes, days,
        project_ids: [], public_key_pem: '' })
      onIssued(issued.key.key_id, issued.private_key_pem)
    }, m.keys_issued())
    if (ok) { setName(''); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.key_issue()}
      submitLabel={m.key_issue()} busy={busy}
      disabled={!owner || !name || scopes.length === 0} onSubmit={submit}>
      <Field label={m.col_user()}>
        <Select value={owner} onChange={setOwner} placeholder={m.choose()}
          options={owners.map((u) => ({ value: u.id, label: `${u.name} · ${u.email}` }))} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={m.col_name()}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={m.key_days()}>
          <Input type="number" min={1} value={days}
            onChange={(e) => setDays(Number(e.target.value))} />
        </Field>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">{m.key_scopes()}</legend>
        <div className="flex flex-wrap gap-4">
          {SCOPES.map((scope) => (
            <Checkbox key={scope} checked={scopes.includes(scope)} label={scopeText[scope]()}
              onChange={(on) => toggle(scope, on)} />
          ))}
        </div>
      </fieldset>
    </FormModal>
  )
}
