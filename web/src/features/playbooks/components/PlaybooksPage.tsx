import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Globe, Languages, ListChecks, Plus, Share2, Workflow } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import {
  cardGridClass, CardsPerRowToggle, isCompact,
} from '../../../components/ui/CardsPerRow.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { Field, Switch, Textarea } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { matches, SearchBox } from '../../../components/ui/SearchBox.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { Tooltip } from '../../../components/ui/Tooltip.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { useCardsPerRow } from '../../../stores/cardsPerRow.ts'
import { cn } from '../../../utils/cn.ts'
import {
  addCustomPlaybook, playbookCatalogQuery, type PlaybookRow, setSystemPlaybook,
} from '../api.ts'
import { localized } from '../localized.ts'
import { AssignDialog } from './AssignDialog.tsx'
import { CardAction, PlaybookCard } from './PlaybookCard.tsx'
import { PlaybooksIntro } from './PlaybooksIntro.tsx'
import { TranslateDialog } from './TranslateDialog.tsx'

function CustomDialog({ open, onOpenChange }: { open: boolean,
  onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [spec, setSpec] = useState('')
  const save = async () => {
    const ok = await run(async () => {
      await addCustomPlaybook(JSON.parse(spec))
      await queryClient.invalidateQueries({ queryKey: ['playbooks'] })
    }, m.pb_custom_added())
    if (ok) { setSpec(''); onOpenChange(false) }
  }
  return (
    <FormModal open={open} onOpenChange={onOpenChange} size="lg" title={m.pb_custom_title()}
      submitLabel={m.action_add()} busy={busy} disabled={!spec} onSubmit={save}>
      <Field label={m.pb_custom_spec()}>
        <Textarea rows={14} className="font-mono text-xs" value={spec} autoFocus
          onChange={(e) => setSpec(e.target.value)} />
      </Field>
    </FormModal>
  )
}

function useSystemSwitch() {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const toggle = async (p: PlaybookRow) => {
    const { title } = localized(p)
    const ok = await confirm({
      title: p.enabled ? m.pb_off_title({ title }) : m.pb_on_title({ title }),
      description: p.enabled ? m.pb_off_text_system() : m.pb_on_text_system(),
      confirmLabel: p.enabled ? m.pb_switch_off() : m.pb_switch_on(),
      tone: p.enabled ? 'destructive' : 'default' })
    if (!ok) return
    await run(async () => {
      await setSystemPlaybook(p.id, !p.enabled)
      await queryClient.invalidateQueries({ queryKey: ['playbooks'] })
    }, p.enabled ? m.pb_switched_off() : m.pb_switched_on())
  }
  return { busy, toggle }
}

type Open = { kind: 'assign' | 'translate', playbook: PlaybookRow } | null

/** Every playbook: what it does, where it may run (assign to projects), its translations;
 * superadmins also switch one for every project and add custom specs. */
export function PlaybooksPage({ superadmin }: { superadmin: boolean }) {
  useDocumentTitle(m.nav_playbooks())
  const catalog = useQuery(playbookCatalogQuery)
  const { busy, toggle } = useSystemSwitch()
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [open, setOpen] = useState<Open>(null)
  const perRow = useCardsPerRow()
  const compact = isCompact(perRow)
  const shown = (catalog.data ?? []).filter((p) => {
    const text = localized(p)
    return matches(query, text.title, p.title, p.id, text.summary)
  })
  const footer = (p: PlaybookRow) => (
    <>
      {superadmin ? (
        <Tooltip text={p.enabled ? m.pb_switch_off() : m.pb_switch_on()}>
          <span><Switch checked={p.enabled} onChange={() => void toggle(p)} disabled={busy}
            label={p.enabled ? m.pb_switch_off() : m.pb_switch_on()} /></span>
        </Tooltip>
      ) : null}
      {compact ? (
        <Tooltip text={p.enabled ? m.pb_assigned_all() : m.pb_assign_selected()} side="top">
          <span tabIndex={0} aria-label={p.enabled ? m.pb_assigned_all() : m.pb_assign_selected()}
            className={cn('grid size-8 place-items-center rounded-md [&_svg]:size-4',
              p.enabled ? 'text-primary' : 'text-muted-foreground')}>
            {p.enabled ? <Globe /> : <ListChecks />}
          </span>
        </Tooltip>
      ) : (
        <Badge tone={p.enabled ? 'success' : 'default'}>
          {p.enabled ? m.pb_assigned_all() : m.pb_assign_selected()}
        </Badge>
      )}
      <CardAction icon={<Share2 />} label={m.pb_assign()} compact={compact}
        onClick={() => setOpen({ kind: 'assign', playbook: p })} />
      {superadmin ? (
        <CardAction variant="ghost" icon={<Languages />} label={m.pb_translate()}
          compact={compact} onClick={() => setOpen({ kind: 'translate', playbook: p })} />
      ) : null}
    </>
  )
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<Workflow />} title={m.nav_playbooks()} description={m.pb_page_intro()}
        actions={superadmin ? (
          <Button onClick={() => setAdding(true)}><Plus />{m.pb_custom_title()}</Button>
        ) : null} />
      <PlaybooksIntro />
      {catalog.error ? <Notice tone="error">{errorText(catalog.error)}</Notice> : null}
      <div className="flex flex-wrap items-center gap-2">
        <SearchBox value={query} onChange={setQuery} />
        <div className="ml-auto"><CardsPerRowToggle /></div>
      </div>
      {catalog.isPending ? <Skeleton className="h-64 rounded-xl" /> : null}
      {!catalog.isPending && shown.length === 0
        ? <EmptyState icon={<Workflow className="size-5" />} text={m.pb_empty()} /> : null}
      <div className="@container">
        <div className={cardGridClass(perRow)}>
          {shown.map((p) => (
            <PlaybookCard key={p.id} playbook={p} compact={compact} footer={footer(p)} />
          ))}
        </div>
      </div>
      {superadmin ? <CustomDialog open={adding} onOpenChange={setAdding} /> : null}
      {open?.kind === 'assign' ? (
        <AssignDialog playbookId={open.playbook.id} title={localized(open.playbook).title}
          superadmin={superadmin} onClose={() => setOpen(null)} />
      ) : null}
      {open?.kind === 'translate' ? (
        <TranslateDialog playbook={open.playbook} onClose={() => setOpen(null)} />
      ) : null}
    </div>
  )
}
