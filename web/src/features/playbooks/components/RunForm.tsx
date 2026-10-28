import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input, Textarea } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { runStatusText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  type ParamSpec, type PlaybookRow, runsQuery, type RunRow, specQuery, startRun,
} from '../api.ts'
import { localized } from '../localized.ts'

function parse(spec: ParamSpec, raw: string): unknown {
  if (spec.type === 'number' || spec.type === 'integer') return raw === '' ? null : Number(raw)
  if (spec.type === 'boolean') return raw === 'true'
  if (spec.type === 'array' || spec.type === 'object') return JSON.parse(raw) as unknown
  return raw
}

function show(value: unknown): string {
  if (value === undefined || value === null) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value as string | number)
}

/** A run form generated from the spec (one field per parameter, a JSON box per input). */
export function RunDialog({ projectId, playbook, version, onClose }: { projectId: string,
  playbook: PlaybookRow, version: number, onClose: () => void }) {
  const spec = useQuery(specQuery(playbook.id, version))
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [values, setValues] = useState<Record<string, string>>({})
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [done, setDone] = useState<RunRow | null>(null)
  const params = spec.data?.params ?? {}
  const send = async () => {
    setDone(null)
    await run(async () => {
      const p = Object.fromEntries(Object.entries(values)
        .filter(([k]) => k in params)
        .map(([k, v]) => [k, parse(params[k] ?? { type: 'string' }, v)]))
      const i = Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, JSON.parse(v)]))
      setDone(await startRun(projectId, playbook.id, version, p, i))
      await queryClient.invalidateQueries({ queryKey: runsQuery(projectId).queryKey })
    }, m.pb_run_started())
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="lg"
      title={m.pb_run_title({ title: localized(playbook).title })}
      description={localized(playbook).summary || spec.data?.summary}
      submitLabel={m.pb_run()} busy={busy} disabled={!spec.data} onSubmit={send}>
      {spec.error ? <Notice tone="error">{errorText(spec.error)}</Notice> : null}
      {spec.isPending ? <Skeleton className="h-32" /> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(params).map(([name, p]) => (
          <Field key={name} label={name} hint={p.doc}>
            <Input placeholder={show(p.default)} value={values[name] ?? ''}
              onChange={(e) => setValues({ ...values, [name]: e.target.value })} />
          </Field>
        ))}
      </div>
      {Object.entries(spec.data?.inputs ?? {}).map(([name, input]) => (
        <Field key={name} label={name} hint={input.doc}>
          <Textarea rows={4} className="font-mono text-xs" value={inputs[name] ?? ''}
            onChange={(e) => setInputs({ ...inputs, [name]: e.target.value })} />
        </Field>
      ))}
      {done ? (
        <Notice tone={done.status === 'failed' ? 'error' : 'ok'}>
          {m.pb_run_status({ status: runStatusText(done.status) })}
          {done.error ? ` · ${done.error}` : ''}
        </Notice>
      ) : null}
    </FormModal>
  )
}
