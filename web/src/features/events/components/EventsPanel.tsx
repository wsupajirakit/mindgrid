import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Radio, Send, Trash2, Truck } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Switch } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  ping, remove, type Scope, setEnabled, type Subscription, subscriptionsQuery,
} from '../api.ts'
import { Deliveries } from './Deliveries.tsx'
import { EventLog } from './EventLog.tsx'
import { ReceiverDialog, SecretDialog } from './ReceiverDialog.tsx'

function useReceiverActions(scope: Scope) {
  const queryClient = useQueryClient()
  const { run } = useAction()
  const refresh = () => queryClient.invalidateQueries({
    queryKey: subscriptionsQuery(scope).queryKey })
  const toggle = async (s: Subscription) => {
    const ok = await confirm({
      title: s.enabled ? m.ev_off_title({ name: s.name }) : m.ev_on_title({ name: s.name }),
      description: s.enabled ? m.ev_off_text() : m.ev_on_text(),
      confirmLabel: s.enabled ? m.pb_switch_off() : m.pb_switch_on(),
      tone: s.enabled ? 'destructive' : 'default' })
    if (ok) await run(async () => { await setEnabled(s.id, !s.enabled); await refresh() },
      s.enabled ? m.pb_switched_off() : m.pb_switched_on())
  }
  const drop = async (s: Subscription) => {
    const ok = await confirm({ title: m.ev_remove_title({ name: s.name }),
      description: m.ev_remove_text(), confirmLabel: m.action_remove(), tone: 'destructive' })
    if (ok) await run(async () => { await remove(s.id); await refresh() }, m.ev_removed())
  }
  const test = (s: Subscription) => run(() => ping(s.id), m.ev_tested())
  return { toggle, drop, test }
}

/** Receivers of this project's events (or system-wide ones), their deliveries, the log. */
export function EventsPanel({ projectId }: { projectId: string | null }) {
  const scope = { projectId }
  const subs = useQuery(subscriptionsQuery(scope))
  const { toggle, drop, test } = useReceiverActions(scope)
  const [adding, setAdding] = useState(false)
  const [secret, setSecret] = useState('')
  const [open, setOpen] = useState<Subscription | null>(null)
  const columns: Column<Subscription>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2 font-medium">
          <Radio className="size-4 text-primary" />{row.original.name}
        </span>
        <code className="truncate text-xs text-muted-foreground">{row.original.url}</code>
      </span>
    ) },
    { id: 'types', accessorFn: (s) => s.event_types.join(' '), header: () => m.ev_types(),
      cell: ({ row }) => (
        <span className="flex flex-wrap gap-1">
          {row.original.event_types.map((t) => (
            <Badge key={t} tone="outline">{t === '*' ? m.ev_all_types() : t}</Badge>
          ))}
        </span>
      ) },
    { accessorKey: 'enabled', header: () => m.col_status(), cell: ({ row }) => (
      <span className="flex flex-col gap-1">
        <Switch checked={row.original.enabled} onChange={() => void toggle(row.original)}
          label={row.original.enabled ? m.pb_switch_off() : m.pb_switch_on()} />
        {row.original.enabled ? null : (
          <span className="text-xs text-muted-foreground">
            {m.ev_off({ reason: row.original.disabled_reason || '—' })}
          </span>
        )}
      </span>
    ) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end gap-1">
        <Button variant="ghost" size="sm" onClick={() => void test(row.original)}>
          <Send />{m.ev_test()}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setOpen(row.original)}>
          <Truck />{m.ev_deliveries()}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label={m.action_remove()}
          onClick={() => void drop(row.original)}><Trash2 /></Button>
      </span>
    ) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <Card title={m.ev_receivers()} description={projectId ? m.ev_intro() : m.ev_system_intro()}
        actions={<Button size="sm" onClick={() => setAdding(true)}><Plus />{m.ev_new()}</Button>}>
        {subs.error ? <Notice tone="error">{errorText(subs.error)}</Notice> : null}
        <DataTable data={subs.data ?? []} columns={columns} empty={m.ev_no_receivers()}
          loading={subs.isPending} />
      </Card>
      {projectId ? <EventLog projectId={projectId} /> : null}
      <ReceiverDialog scope={scope} open={adding} onOpenChange={setAdding} onSecret={setSecret} />
      {secret ? <SecretDialog secret={secret} onClose={() => setSecret('')} /> : null}
      {open ? <Deliveries subscription={open} onClose={() => setOpen(null)} /> : null}
    </div>
  )
}
