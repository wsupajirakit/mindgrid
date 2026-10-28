import { CircleAlert, CircleCheck } from 'lucide-react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { DetailSection } from '../../../components/ui/Detail.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { StatCard } from '../../../components/ui/StatCard.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import type { EvalRun } from '../api.ts'

export const METRICS = ['hit_at_k', 'recall_at_k', 'mrr', 'ndcg_at_k', 'abstention'] as const
const JUDGE_METRICS = ['judge_context', 'judge_faithfulness'] as const
type Case = { query: string, expect: string[], found: string[], hit: number,
  abstained: boolean | null }

const MUTED = 'px-3 py-2 text-xs text-muted-foreground'

export const score = (run: EvalRun, key: string) => (run.metrics[key] ?? 0).toFixed(2)

function Judgement({ run }: { run: EvalRun }) {
  const latest = run.judgements?.[0]
  if (!latest) {
    return run.judging ? <Notice>{m.eval_judging({ mode: run.judging })}</Notice> : null
  }
  return (
    <DetailSection title={m.eval_judgement()}>
      <div className="flex flex-wrap items-center gap-2">
        {JUDGE_METRICS.map((k) => (
          <Badge key={k} tone="primary">{`${k} ${(latest.metrics[k] ?? 0).toFixed(2)}`}</Badge>
        ))}
        <span className="text-xs text-muted-foreground">
          {m.eval_judged_by({ judge: latest.judge, answerer: latest.answerer || '—' })}
        </span>
      </div>
    </DetailSection>
  )
}

function Cases({ run }: { run: EvalRun }) {
  const cases = run.cases as unknown as Case[]
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            {[m.eval_result(), m.eval_query(), m.eval_expect(), m.eval_found()].map((h) => (
              <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map((c, i) => {
            const ok = c.abstained === null ? c.hit >= 1 : c.abstained
            return (
              <tr key={`${c.query}-${String(i)}`} className="border-t border-border align-top">
                <td className="px-3 py-2">
                  <Badge tone={ok ? 'success' : 'destructive'}>
                    {ok ? <CircleCheck className="size-3" /> : <CircleAlert className="size-3" />}
                    {ok ? m.eval_pass() : m.eval_miss()}
                  </Badge>
                </td>
                <td className="px-3 py-2 font-medium">{c.query}</td>
                <td className={MUTED}>{c.expect.join(', ') || '—'}</td>
                <td className={MUTED}>{c.found.join(', ') || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** One eval run: its scores, the LLM judgement (if any) and every question's outcome. */
export function EvalDetail({ run, onClose }: { run: EvalRun, onClose: () => void }) {
  const { dateTime } = useFormat()
  const setup = String(run.setup.reranker ?? '') || String(run.setup.space ?? '')
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="xl" title={run.name}
      description={[dateTime(run.created_at), `k=${String(run.k)}`, setup].filter(Boolean)
        .join(' · ')}>
      <div className="flex flex-col gap-5">
        <DetailSection title={m.eval_metrics()}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {METRICS.map((k) => <StatCard key={k} label={k} value={score(run, k)} />)}
          </div>
        </DetailSection>
        <Judgement run={run} />
        <DetailSection title={m.eval_cases()}><Cases run={run} /></DetailSection>
      </div>
    </Modal>
  )
}
