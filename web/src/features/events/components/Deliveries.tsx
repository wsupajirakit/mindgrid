import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { Badge, type BadgeTone } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { deliveryStatusText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Delivery, deliveriesQuery, replay } from '../api.ts'

const TONE: Record<string, BadgeTone> = { delivered: 'success', dead: 'destructive',
  pending: 'warning', retrying: 'warning' }

/** Recent deliveries of one receiver; dead or delivered ones can be sent again. */
export function Deliveries({ subscription, onClose }: {
  subscription: { id: string, name: string }, onClose: () => void }) {
  const rows = useQuery(deliveriesQuery(subscription.id))
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const { run } = useAction()
  const again = async (d: Delivery) => {
    const ok = await confirm({ title: m.ev_replay_title(), description: m.ev_replay_text(),
      confirmLabel: m.ev_replay() })
    if (!ok) return
    await run(async () => {
      await replay(d.id)
      await queryClient.invalidateQueries({ queryKey: deliveriesQuery(subscription.id).queryKey })
    }, m.ev_replayed())
  }
  const columns: Column<Delivery>[] = [
    { accessorKey: 'status', header: () => m.col_status(), cell: ({ row }) => (
      <Badge tone={TONE[row.original.status] ?? 'default'}>
        {deliveryStatusText(row.original.status)}
      </Badge>
    ) },
    { accessorKey: 'next_attempt_at', header: () => m.ev_next_attempt(),
      cell: ({ row }) => dateTime(row.original.next_attempt_at) },
    { accessorKey: 'attempts', header: () => m.ev_deliveries(), cell: ({ row }) => (
      <span className="flex flex-col gap-0.5 text-xs">
        {m.ev_attempts({ n: String(row.original.attempts),
          code: String(row.original.last_status_code ?? '—') })}
        {row.original.last_error
          ? <span className="text-destructive">{row.original.last_error}</span> : null}
      </span>
    ) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) =>
      row.original.status === 'dead' || row.original.status === 'delivered' ? (
        <span className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={() => void again(row.original)}>
            <Send />{m.ev_replay()}
          </Button>
        </span>
      ) : null },
  ]
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="xl"
      title={m.ev_deliveries_of({ name: subscription.name })}>
      {rows.error ? <Notice tone="error">{errorText(rows.error)}</Notice> : null}
      <DataTable data={rows.data ?? []} columns={columns} empty={m.ev_no_deliveries()}
        loading={rows.isPending} />
    </Modal>
  )
}
