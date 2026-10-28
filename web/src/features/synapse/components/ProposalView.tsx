import { useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, ChevronUp, X } from 'lucide-react'
import { useState } from 'react'
import { Badge, type BadgeTone } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { decide, type Proposal, proposalsQuery, tasksHref } from '../api.ts'

type Item = { kind: string, path: string, summary: string, decision: string,
  detail: { diff?: string, text?: string, functions?: string[] } }
const DECISION: Record<string, BadgeTone> = { accepted: 'success', rejected: 'destructive' }

/** One proposal: every item with what changed (sanitised), accepted or rejected one by one. */
export function ProposalView({ proposal }: { proposal: Proposal }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [open, setOpen] = useState(-1)
  const items = proposal.items as unknown as Item[]
  const act = async (index: number, item: Item, accept: boolean) => {
    const ok = await confirm({
      title: accept ? m.syn_accept_title() : m.syn_reject_title(),
      description: accept ? m.syn_accept_text({ path: item.path })
        : m.syn_reject_text({ path: item.path }),
      confirmLabel: accept ? m.syn_accept() : m.syn_reject(),
      tone: accept ? 'default' : 'destructive' })
    if (!ok) return
    await run(async () => {
      await decide(proposal.id, index, accept)
      await queryClient.invalidateQueries({ queryKey: proposalsQuery.queryKey })
    }, accept ? m.syn_accepted() : m.syn_rejected())
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        {m.syn_commits({ from: proposal.from_commit.slice(0, 10) || '—',
          to: proposal.to_commit.slice(0, 10), redacted: String(proposal.redactions) })}
        {' · '}
        <a className="text-primary hover:underline" href={tasksHref(proposal.id)}>
          {m.syn_tasks()}
        </a>
      </p>
      <ol className="flex flex-col gap-2">
        {items.map((item, i) => (
          <li key={`${item.kind}-${item.path}-${String(i)}`}
            className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="primary">{item.kind}</Badge>
              <code className="text-xs">{item.path}</code>
              <span className="text-muted-foreground">{item.summary}</span>
              {item.decision === 'pending' ? null
                : <Badge tone={DECISION[item.decision] ?? 'default'}>{item.decision}</Badge>}
              <span className="flex-1" />
              <Button variant="ghost" size="sm" onClick={() => setOpen(open === i ? -1 : i)}>
                {open === i ? <ChevronUp /> : <ChevronDown />}
                {open === i ? m.syn_hide() : m.syn_show()}
              </Button>
              {item.decision === 'pending' ? (
                <>
                  <Button size="sm" disabled={busy} onClick={() => void act(i, item, true)}>
                    <Check />{m.syn_accept()}
                  </Button>
                  <Button variant="outline" size="sm" disabled={busy}
                    onClick={() => void act(i, item, false)}><X />{m.syn_reject()}</Button>
                </>
              ) : null}
            </div>
            {open === i ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-3 text-xs">
                {item.detail.diff ?? item.detail.text ?? ''}
              </pre>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}
