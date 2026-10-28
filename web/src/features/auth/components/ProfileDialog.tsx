import { useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { useState } from 'react'
import { Avatar, AVATAR_IDS, AvatarArt } from '../../../components/ui/Avatar.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { cn } from '../../../utils/cn.ts'
import { type Me, meQuery, updateProfile } from '../api.ts'

/** Name and picture of the signed-in account (pictures from the built-in set). */
export function ProfileDialog({ me, open, onOpenChange }: { me: Me, open: boolean,
  onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [name, setName] = useState(me.display_name)
  const [avatar, setAvatar] = useState(me.avatar ?? '')
  const save = async () => {
    const ok = await run(async () => {
      queryClient.setQueryData(meQuery.queryKey,
        await updateProfile({ display_name: name, avatar }))
    })
    if (ok) onOpenChange(false)
  }
  const choice = (id: string, picture: React.ReactNode, label: string) => (
    <button key={id || 'initials'} type="button" aria-label={label} aria-pressed={avatar === id}
      onClick={() => setAvatar(id)}
      className={cn('relative size-14 overflow-hidden rounded-full ring-2 ring-transparent',
        'transition hover:scale-105', avatar === id && 'ring-primary ring-offset-2',
        'ring-offset-popover')}>
      {picture}
      {avatar === id ? (
        <span className="absolute inset-0 grid place-items-center bg-black/30 text-white">
          <Check className="size-5" />
        </span>
      ) : null}
    </button>
  )
  return (
    <FormModal open={open} onOpenChange={onOpenChange} title={m.account_profile()}
      submitLabel={m.action_save()} busy={busy} disabled={!name.trim()} onSubmit={save}>
      <div className="flex items-center gap-4">
        <Avatar name={name || me.email} avatar={avatar} size="xl" />
        <div className="min-w-0">
          <p className="truncate font-semibold">{name || me.email}</p>
          <p className="truncate text-sm text-muted-foreground">{me.email}</p>
        </div>
      </div>
      <Field label={m.account_name()}>
        <Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
      </Field>
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">{m.account_pick_avatar()}</span>
        <div className="flex flex-wrap gap-3">
          {choice('', <Avatar name={name || me.email} size="lg" className="ring-0" />,
            m.account_initials())}
          {AVATAR_IDS.map((id) => choice(id, <AvatarArt id={id} className="size-full" />, id))}
        </div>
      </div>
    </FormModal>
  )
}
