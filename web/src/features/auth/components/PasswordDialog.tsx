import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { NewPassword } from '../../../components/ui/NewPassword.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { passwordReady } from '../../../utils/passwordRules.ts'
import { changePassword } from '../api.ts'

const EMPTY = { current: '', next: '', repeat: '' }

/** Change your own password; other sign-ins end, this one stays. */
export function PasswordDialog({ open, onOpenChange }: { open: boolean,
  onOpenChange: (open: boolean) => void }) {
  const { busy, run } = useAction()
  const [form, setForm] = useState(EMPTY)
  const save = async () => {
    const ok = await run(() => changePassword(form.current, form.next),
      m.account_password_changed())
    if (ok) { setForm(EMPTY); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.account_password()}
      size="sm" submitLabel={m.action_save()} busy={busy}
      disabled={!form.current || !passwordReady(form.next, form.repeat)} onSubmit={save}>
      <Notice>{m.account_password_note()}</Notice>
      <Field label={m.account_current_password()}>
        <Input type="password" autoComplete="current-password" value={form.current}
          onChange={(e) => setForm({ ...form, current: e.target.value })} />
      </Field>
      <NewPassword label={m.account_new_password()} repeatLabel={m.account_repeat_password()}
        value={form.next} repeat={form.repeat}
        onChange={(next) => setForm({ ...form, next })}
        onRepeatChange={(repeat) => setForm({ ...form, repeat })} />
    </FormModal>
  )
}
