import { useQuery } from '@tanstack/react-query'
import { CircleAlert, CircleCheck } from 'lucide-react'
import { Badge, type BadgeTone } from '../../../components/ui/Badge.tsx'
import { DetailSection, JsonBlock } from '../../../components/ui/Detail.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { playbookStatusText, runStatusText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { runQuery, type RunRow } from '../api.ts'

const TONE: Record<string, BadgeTone> = { done: 'success', failed: 'destructive',
  queued: 'default', running: 'warning' }

export function RunStatusBadge({ status }: { status: string }) {
  return <Badge tone={TONE[status] ?? 'default'}>{runStatusText(status)}</Badge>
}

/** What a run was given, each step it took, and what it produced. */
function RunBody({ run }: { run: RunRow }) {
  const { dateTime } = useFormat()
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <RunStatusBadge status={run.status} />
        <Badge tone="outline">{`v${String(run.playbook_version)} · ${
          playbookStatusText(run.playbook_status)}`}</Badge>
        <span className="text-muted-foreground">
          {`${dateTime(run.created_at)}${run.finished_at
            ? ` → ${m.runs_finished()} ${dateTime(run.finished_at)}` : ''}`}
        </span>
      </div>
      {run.error ? <Notice tone="error">{run.error}</Notice> : null}
      <DetailSection title={m.runs_params()}><JsonBlock value={run.params} /></DetailSection>
      <DetailSection title={m.runs_inputs()}><JsonBlock value={run.inputs ?? {}} /></DetailSection>
      <DetailSection title={m.res_steps()}>
        <ol className="flex flex-col gap-1 text-sm">
          {run.steps.map((s) => (
            <li key={String(s.id)} className="flex items-center gap-2">
              {s.ok ? <CircleCheck className="size-4 text-success" />
                : <CircleAlert className="size-4 text-destructive" />}
              <code className="text-xs">{String(s.id)}</code>
              <span className="text-muted-foreground">{String(s.fn)}</span>
              {s.ok ? null : <span className="text-xs text-destructive">{String(s.error)}</span>}
              <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                {m.res_ms({ n: String(s.ms) })}
              </span>
            </li>
          ))}
        </ol>
      </DetailSection>
      <DetailSection title={m.res_outputs()}><JsonBlock value={run.outputs} /></DetailSection>
    </div>
  )
}

/** A run fetched by id (kept fresh while it is queued or running). */
export function RunById({ id }: { id: string }) {
  const run = useQuery(runQuery(id))
  if (run.error) return <Notice tone="error">{errorText(run.error)}</Notice>
  if (!run.data) return <Skeleton className="h-40" />
  return <RunBody run={run.data} />
}
