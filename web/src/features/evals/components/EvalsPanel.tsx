import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FlaskConical, Play } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Textarea } from '../../../components/ui/Field.tsx'
import { ALL, Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { EXAMPLE, type EvalRun, evalsQuery, runEval } from '../api.ts'
import { EvalDetail, METRICS, score } from './EvalDetail.tsx'

const JUDGES = ['', 'local', 'gemini'] as const
type Judge = (typeof JUDGES)[number]

function NewEvalDialog({ projectId, open, onOpenChange, onDone }: { projectId: string,
  open: boolean, onOpenChange: (open: boolean) => void, onDone: (run: EvalRun) => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [golden, setGolden] = useState(EXAMPLE)
  const [judge, setJudge] = useState<Judge>('')
  const send = () => run(async () => {
    const body = { ...(JSON.parse(golden) as object), ...(judge ? { judge } : {}) }
    const done = await runEval(projectId, body)
    await queryClient.invalidateQueries({ queryKey: evalsQuery(projectId).queryKey })
    onOpenChange(false)
    onDone(done)
  }, m.eval_done())
  return (
    <FormModal open={open} onOpenChange={onOpenChange} size="lg" title={m.eval_new()}
      description={m.eval_intro()} submitLabel={m.eval_run()} busy={busy}
      onSubmit={async () => { await send() }}>
      <Field label={m.eval_golden()}>
        <Textarea rows={12} className="font-mono text-xs" value={golden}
          onChange={(e) => setGolden(e.target.value)} />
      </Field>
      <Field label={m.eval_judge()}>
        <Select value={judge || ALL} onChange={(v) => setJudge((v === ALL ? '' : v) as Judge)}
          options={JUDGES.map((j) => ({ value: j || ALL, label: j || m.eval_judge_off() }))} />
      </Field>
    </FormModal>
  )
}

/** Retrieval evals: golden questions scored without any LLM, kept run by run; an LLM judge
 * may grade a run as well. */
export function EvalsPanel({ projectId }: { projectId: string }) {
  const runs = useQuery(evalsQuery(projectId))
  const { dateTime } = useFormat()
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<EvalRun | null>(null)
  const columns: Column<EvalRun>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <FlaskConical className="size-4 text-primary" />{row.original.name}
      </span>
    ) },
    { accessorKey: 'created_at', header: () => m.col_when(),
      cell: ({ row }) => dateTime(row.original.created_at) },
    ...METRICS.map((k): Column<EvalRun> => ({ id: k, accessorFn: (r) => r.metrics[k] ?? 0,
      header: () => k, cell: ({ row }) => (
        <span className="tabular-nums">{score(row.original, k)}</span>) })),
    { id: 'judge', accessorFn: (r) => r.judgements?.[0]?.judge ?? '', header: () => m.eval_judge(),
      cell: ({ row }) => {
        const latest = row.original.judgements?.[0]
        if (latest) return <Badge tone="primary">{latest.judge}</Badge>
        return row.original.judging ? <Badge tone="warning">{row.original.judging}</Badge> : '—'
      } },
  ]
  return (
    <Card title={m.eval_runs()} description={m.eval_intro()} actions={(
      <Button size="sm" onClick={() => setCreating(true)}><Play />{m.eval_new()}</Button>
    )}>
      {runs.error ? <Notice tone="error">{errorText(runs.error)}</Notice> : null}
      <DataTable data={runs.data ?? []} columns={columns} empty={m.eval_empty()}
        loading={runs.isPending} onRowClick={setOpen} />
      <NewEvalDialog projectId={projectId} open={creating} onOpenChange={setCreating}
        onDone={setOpen} />
      {open ? <EvalDetail run={runs.data?.find((r) => r.id === open.id) ?? open}
        onClose={() => setOpen(null)} /> : null}
    </Card>
  )
}
