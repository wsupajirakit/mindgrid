import { useQuery } from '@tanstack/react-query'
import { CircleAlert, CircleCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { DetailSection } from '../../../components/ui/Detail.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Call, questionQuery } from '../api.ts'

function QuestionBody({ id }: { id: string }) {
  const detail = useQuery(questionQuery(id))
  const { dateTime } = useFormat()
  if (detail.error) return <Notice tone="error">{errorText(detail.error)}</Notice>
  if (!detail.data) return <Skeleton className="h-40" />
  const q = detail.data
  return (
    <div className="flex flex-col gap-5">
      <blockquote className="rounded-lg border-l-4 border-primary bg-accent/40 p-3 text-sm">
        {q.query}
      </blockquote>
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge tone="outline">{q.via}</Badge>
        <Badge>{m.res_ms({ n: String(q.ms) })}</Badge>
        <Badge>{m.res_hits({ n: String(q.passages.length) })}</Badge>
      </div>
      <DetailSection title={m.res_answers()}>
        {q.answers.length === 0 ? <Notice>{m.res_no_answer()}</Notice> : q.answers.map((a) => (
          <div key={a.id} className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <p className="text-xs text-muted-foreground">
              {`${dateTime(a.at)} · `}{m.res_by({ writer: a.writer, channel: a.channel })}
            </p>
            <p className="text-sm whitespace-pre-wrap">{a.text}</p>
            <p className={a.check_ok ? 'flex items-center gap-1.5 text-xs text-success'
              : 'flex items-center gap-1.5 text-xs text-warning'}>
              {a.check_ok ? <CircleCheck className="size-3.5" />
                : <CircleAlert className="size-3.5" />}
              {a.check_ok ? m.res_check_ok() : m.res_check_bad({
                unknown: String(a.unknown.length), uncited: String(a.uncited) })}
            </p>
          </div>
        ))}
      </DetailSection>
      <DetailSection title={m.res_passages()}>
        <ol className="flex flex-col gap-2">
          {q.passages.map((p) => (
            <li key={p.ref} className="rounded-lg border border-border p-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Badge tone="primary">{p.ref}</Badge>
                <span className="font-medium">{p.title}</span>
                {p.heading ? <span className="text-muted-foreground">{p.heading}</span> : null}
              </div>
              <p className="line-clamp-4 whitespace-pre-wrap text-muted-foreground">{p.text}</p>
            </li>
          ))}
        </ol>
      </DetailSection>
    </div>
  )
}

/** Everything about one call: the question with its passages and answers, or the run
 * (`runBody` renders a run; the page composes it from the playbooks feature). */
export function CallDetail({ call, onClose, footer, runBody }: { call: Call,
  onClose: () => void, footer?: ReactNode, runBody: (id: string) => ReactNode }) {
  const { dateTime } = useFormat()
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="lg" footer={footer}
      title={call.kind === 'run' ? call.title : m.res_kind_question()}
      description={[dateTime(call.at), call.actor?.name ?? m.res_someone(), call.project]
        .join(' · ')}>
      {call.kind === 'run' ? runBody(call.id) : <QuestionBody id={call.id} />}
    </Modal>
  )
}
