import { CircleAlert, CircleCheck, Info } from 'lucide-react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { retrieverText, trustText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import type { Answer, Pack } from '../api.ts'

function Passages({ pack }: { pack: Pack }) {
  if (pack.passages.length === 0) return <EmptyState text={m.ask_no_hits()} />
  return (
    <ol className="flex flex-col gap-3">
      {pack.passages.map((p) => (
        <li key={p.ref} id={`passage-${p.ref}`}
          className="rounded-lg border border-border bg-background/40 p-4 text-sm">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="primary">{p.ref}</Badge>
            <span className="font-medium">{p.title}</span>
            {p.heading ? <span className="text-muted-foreground">{p.heading}</span> : null}
            <Badge tone="outline">{trustText(p.trust)}</Badge>
            {p.relevance === null ? null : (
              <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                {m.ask_relevance({ value: p.relevance.toFixed(2) })}
              </span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-muted-foreground">{p.text}</p>
        </li>
      ))}
    </ol>
  )
}

function Notes({ pack }: { pack: Pack }) {
  const skipped = Object.entries(pack.skipped).map(([name, reason]) =>
    m.ask_skipped({ retriever: retrieverText(name), reason }))
  const notes = pack.dropped > 0 ? [...skipped, m.ask_dropped({ n: String(pack.dropped) })]
    : skipped
  if (notes.length === 0) return null
  return (
    <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
      {notes.map((n) => (
        <li key={n} className="flex items-center gap-1.5"><Info className="size-3.5" />{n}</li>
      ))}
    </ul>
  )
}

function Written({ done }: { done: Answer }) {
  if (done.answer === null) return null
  const check = done.check
  return (
    <Card title={m.ask_answer()} description={m.ask_writer({ writer: done.writer })}>
      <p className="text-sm leading-relaxed whitespace-pre-wrap">{done.answer}</p>
      {check ? (
        <p className={check.ok ? 'mt-4 flex items-center gap-1.5 text-sm text-success'
          : 'mt-4 flex items-center gap-1.5 text-sm text-warning'}>
          {check.ok ? <CircleCheck className="size-4" /> : <CircleAlert className="size-4" />}
          {check.ok ? m.ask_check_ok() : m.ask_check_bad({
            unknown: String(check.unknown.length), uncited: String(check.uncited.length) })}
        </p>
      ) : null}
    </Card>
  )
}

/** A question's outcome: the written answer (when asked for) above the passages. */
export function AskResult({ pack, done }: { pack: Pack, done: Answer | null }) {
  return (
    <div className="flex flex-col gap-4">
      {done ? <Written done={done} /> : null}
      <Card title={m.ask_passages()}>
        <div className="flex flex-col gap-3">
          <Notes pack={pack} />
          <Passages pack={pack} />
        </div>
      </Card>
    </div>
  )
}
