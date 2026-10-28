import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Plus, Trash2, Workflow } from 'lucide-react'
import { useState } from 'react'
import { Button, buttonClass } from '../../../components/ui/Button.tsx'
import {
  cardGridClass, CardsPerRowToggle, isCompact,
} from '../../../components/ui/CardsPerRow.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { matches, SearchBox } from '../../../components/ui/SearchBox.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { useCardsPerRow } from '../../../stores/cardsPerRow.ts'
import { type PlaybookRow, playbooksQuery, setEnabled } from '../api.ts'
import { localized } from '../localized.ts'
import { AddPlaybookDialog } from './AddPlaybookDialog.tsx'
import { CardAction, PlaybookCard } from './PlaybookCard.tsx'
import { PlaybooksIntro } from './PlaybooksIntro.tsx'
import { RunDialog } from './RunForm.tsx'

const RUNNABLE = new Set(['provisional', 'active'])

function newest(p: PlaybookRow): number | null {
  const usable = p.versions.filter((v) => RUNNABLE.has(v.status)).map((v) => v.version)
  return p.pinned_version ?? (usable.length ? Math.max(...usable) : null)
}

/** The playbooks this project has (a project starts with none): run each in a modal; a
 * project manager (`canManage`) adds them from the catalog or removes them. */
export function PlaybooksPanel({ projectId, canManage = false }: { projectId: string,
  canManage?: boolean }) {
  const playbooks = useQuery(playbooksQuery(projectId))
  const queryClient = useQueryClient()
  const { run } = useAction()
  const [adding, setAdding] = useState(false)
  const [query, setQuery] = useState('')
  const [running, setRunning] = useState<{ playbook: PlaybookRow, version: number } | null>(null)
  const perRow = useCardsPerRow()
  const compact = isCompact(perRow)
  if (playbooks.error) return <Notice tone="error">{errorText(playbooks.error)}</Notice>
  const assigned = (playbooks.data ?? []).filter((p) => p.enabled)
  const drop = async (p: PlaybookRow) => {
    const ok = await confirm({ title: m.pb_remove_title({ title: localized(p).title }),
      description: m.pb_remove_text(), confirmLabel: m.action_remove(), tone: 'destructive' })
    if (ok) await run(async () => {
      await setEnabled(projectId, p.id, false, p.params, p.pinned_version)
      await queryClient.invalidateQueries({ queryKey: playbooksQuery(projectId).queryKey })
    }, m.pb_removed())
  }
  const shown = assigned.filter((p) => {
    const text = localized(p)
    return matches(query, text.title, p.title, p.id, text.summary)
  })
  return (
    <div className="flex flex-col gap-4">
      <PlaybooksIntro />
      <div className="flex flex-wrap items-center gap-2">
        {assigned.length > 0 ? <SearchBox value={query} onChange={setQuery} /> : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {assigned.length > 0 ? <CardsPerRowToggle /> : null}
          {canManage ? (
            <Button onClick={() => setAdding(true)}><Plus />{m.pb_add()}</Button>
          ) : null}
        </div>
      </div>
      {playbooks.isPending ? <Skeleton className="h-64 rounded-xl" /> : null}
      {!playbooks.isPending && shown.length === 0 ? (
        <EmptyState icon={<Workflow className="size-5" />}
          text={assigned.length === 0 ? m.pb_project_empty() : m.ui_no_results()}
          action={assigned.length === 0 && !canManage ? (
            <Link to="/playbooks" className={buttonClass('outline', 'sm')}>
              {m.pb_open_catalog()}
            </Link>
          ) : undefined} />
      ) : null}
      <div className="@container">
        <div className={cardGridClass(perRow)}>
          {shown.map((p) => {
            const version = newest(p)
            return (
              <PlaybookCard key={p.id} playbook={p} compact={compact} footer={canManage ? (
                <CardAction variant="ghost" className="text-destructive" icon={<Trash2 />}
                  label={m.action_remove()} compact={compact} onClick={() => void drop(p)} />
              ) : undefined}
                onRun={version === null ? undefined
                  : () => setRunning({ playbook: p, version })} />
            )
          })}
        </div>
      </div>
      {adding ? <AddPlaybookDialog projectId={projectId}
        available={(playbooks.data ?? []).filter((p) => !p.enabled)}
        onClose={() => setAdding(false)} /> : null}
      {running ? (
        <RunDialog projectId={projectId} playbook={running.playbook} version={running.version}
          onClose={() => setRunning(null)} />
      ) : null}
    </div>
  )
}
