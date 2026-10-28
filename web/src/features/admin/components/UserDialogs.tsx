import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox, Field, FieldGroup, Input } from '../../../components/ui/Field.tsx'
import { NewPassword } from '../../../components/ui/NewPassword.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { passwordReady } from '../../../utils/passwordRules.ts'
import { createUser, resetPassword, setUserGroups, usersQuery } from '../api.ts'

export type GroupChoice = { id: string, name: string }
export type UserRow = { id: string, email: string, display_name: string, system_role: string,
  status: 'active' | 'disabled', last_login_at?: string | null, avatar?: string,
  groups?: GroupChoice[] }
const EMPTY = { email: '', name: '', password: '', repeat: '' }

/** Tick the groups a person belongs to (each group's rights apply to them). */
function GroupChecklist({ groups, picked, onChange }: { groups: GroupChoice[],
  picked: string[], onChange: (ids: string[]) => void }) {
  if (groups.length === 0) return <Notice>{m.groups_none_yet()}</Notice>
  return (
    <div className="grid max-h-56 gap-2 overflow-y-auto rounded-lg border border-border p-3
      sm:grid-cols-2">
      {groups.map((g) => (
        <Checkbox key={g.id} checked={picked.includes(g.id)} label={g.name}
          onChange={(on) => onChange(on ? [...picked, g.id] : picked.filter((x) => x !== g.id))} />
      ))}
    </div>
  )
}

export function NewUserDialog({ open, onOpenChange, groups }: { open: boolean,
  onOpenChange: (open: boolean) => void, groups: GroupChoice[] }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [form, setForm] = useState(EMPTY)
  const [picked, setPicked] = useState<string[]>([])
  const save = async () => {
    const ok = await run(async () => {
      await createUser(form.email, form.password, form.name, picked)
      await queryClient.invalidateQueries({ queryKey: usersQuery.queryKey })
      await queryClient.invalidateQueries({ queryKey: ['groups'] })
    }, m.users_created())
    if (ok) { setForm(EMPTY); setPicked([]); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.users_new()} size="lg"
      submitLabel={m.action_create()} busy={busy}
      disabled={!form.email || !passwordReady(form.password, form.repeat)} onSubmit={save}>
      <Field label={m.col_name()}>
        <Input value={form.name} autoFocus
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label={m.field_email()}>
        <Input type="email" value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })} />
      </Field>
      <NewPassword value={form.password} repeat={form.repeat}
        onChange={(password) => setForm({ ...form, password })}
        onRepeatChange={(repeat) => setForm({ ...form, repeat })} />
      <FieldGroup label={m.groups_of_user()} hint={m.groups_of_user_hint()}>
        <GroupChecklist groups={groups} picked={picked} onChange={setPicked} />
      </FieldGroup>
    </FormModal>
  )
}

export function UserGroupsDialog({ user, groups, onClose }: { user: UserRow,
  groups: GroupChoice[], onClose: () => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [picked, setPicked] = useState((user.groups ?? []).map((g) => g.id))
  const save = async () => {
    const ok = await run(async () => {
      await setUserGroups(user.id, picked)
      await queryClient.invalidateQueries({ queryKey: usersQuery.queryKey })
      await queryClient.invalidateQueries({ queryKey: ['groups'] })
    }, m.groups_user_saved())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }}
      title={m.groups_of_named({ name: user.display_name })}
      description={m.groups_of_user_hint()} submitLabel={m.action_save()} busy={busy}
      onSubmit={save}>
      <GroupChecklist groups={groups} picked={picked} onChange={setPicked} />
    </FormModal>
  )
}

export function ResetDialog({ user, onClose }: { user: UserRow, onClose: () => void }) {
  const { busy, run } = useAction()
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const save = async () => {
    if (await run(() => resetPassword(user.id, password), m.users_reset_done())) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="sm"
      title={m.users_reset_for({ name: user.display_name })} submitLabel={m.users_reset()}
      busy={busy} disabled={!passwordReady(password, repeat)} onSubmit={save}>
      <Notice tone="warn">{m.users_reset_note()}</Notice>
      <NewPassword label={m.account_new_password()} value={password} repeat={repeat}
        onChange={setPassword} onRepeatChange={setRepeat} autoFocus />
    </FormModal>
  )
}
