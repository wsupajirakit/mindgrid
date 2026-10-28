import { useForm } from '@tanstack/react-form'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Activity, BadgeCheck, KeyRound, Workflow } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import * as z from 'zod/mini'
import { Button } from '../../../components/ui/Button.tsx'
import { Cover } from '../../../components/ui/Cover.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { TopProgress } from '../../../components/ui/TopProgress.tsx'
import { useBrand, useDocumentTitle } from '../../../hooks/useBrand.ts'
import { useDelayedFlag } from '../../../hooks/useDelayedFlag.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { meQuery, signIn } from '../api.ts'

const schema = z.object({ email: z.string().check(z.minLength(3)),
  password: z.string().check(z.minLength(1)) })

function Point({ icon, text }: { icon: ReactNode, text: string }) {
  return (
    <li className="flex items-center gap-3 text-sm text-white/90">
      <span className="grid size-8 place-items-center rounded-lg bg-white/15 [&_svg]:size-4">
        {icon}
      </span>
      {text}
    </li>
  )
}

function Showcase({ name }: { name: string }) {
  return (
    <Cover seed={name || 'brand'} className="hidden lg:block">
      <div className="flex h-full flex-col justify-between bg-gradient-to-t from-black/60
        to-black/10 p-10 text-white">
        <span className="flex items-center gap-2.5 text-lg font-semibold">
          <span className="grid size-9 place-items-center rounded-lg bg-white/20">
            <Activity className="size-4" />
          </span>
          {name}
        </span>
        <div className="flex flex-col gap-6">
          <p className="max-w-md text-3xl font-semibold tracking-tight">{m.signin_intro()}</p>
          <ul className="flex flex-col gap-3">
            <Point icon={<BadgeCheck />} text={m.signin_point_1()} />
            <Point icon={<Workflow />} text={m.signin_point_2()} />
            <Point icon={<KeyRound />} text={m.signin_point_3()} />
          </ul>
        </div>
      </div>
    </Cover>
  )
}

const SLOW_MS = 4000 // then a slow server gets a word, not a frozen-looking form

function SubmitArea({ busy, failure }: { busy: boolean, failure: string }) {
  const slow = useDelayedFlag(busy, SLOW_MS)
  return (
    <>
      {failure && !busy ? <Notice tone="error">{failure}</Notice> : null}
      {slow ? <p role="status" className="text-sm text-muted-foreground">{m.signin_slow()}</p>
        : null}
      <Button type="submit" size="lg" loading={busy}>
        {busy ? m.signin_busy() : m.signin_submit()}
      </Button>
    </>
  )
}

export function SignInPage() {
  const brand = useBrand()
  const name = brand?.name ?? ''
  useDocumentTitle(m.signin_title({ brand: name }))
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [failure, setFailure] = useState('')
  const form = useForm({
    defaultValues: { email: '', password: '' },
    validators: { onSubmit: schema },
    onSubmit: async ({ value }) => {
      setFailure('')
      try {
        queryClient.setQueryData(meQuery.queryKey, await signIn(value.email, value.password))
        await navigate({ to: '/dashboard' })
      } catch (error) {
        setFailure(errorText(error))
      }
    },
  })
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <Showcase name={name} />
      <div className="grid place-items-center p-6">
        <form className="relative w-full max-w-sm"
          onSubmit={(e) => { e.preventDefault(); void form.handleSubmit() }}>
          <form.Subscribe selector={(s) => s.isSubmitting}>{(busy) => (
            <fieldset disabled={busy} aria-busy={busy} className="flex flex-col gap-5">
              <TopProgress active={busy} label={m.signin_busy()}
                className="-top-6 rounded-full" />
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {m.signin_title({ brand: name })}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">{m.signin_intro()}</p>
              </div>
              <form.Field name="email">{(field) => (
                <Field label={m.field_email()}>
                  <Input type="email" autoComplete="username" value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)} required />
                </Field>
              )}</form.Field>
              <form.Field name="password">{(field) => (
                <Field label={m.field_password()}>
                  <Input type="password" autoComplete="current-password"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)} required />
                </Field>
              )}</form.Field>
              <SubmitArea busy={busy} failure={failure} />
            </fieldset>
          )}</form.Subscribe>
        </form>
      </div>
    </main>
  )
}
