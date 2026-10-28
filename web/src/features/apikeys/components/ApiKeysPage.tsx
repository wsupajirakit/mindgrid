import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus, RefreshCw, ShieldOff } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { CopyField } from '../../../components/ui/CopyField.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { Person } from '../../../components/ui/Person.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { keysQuery, revokeKey, rotateKey } from '../api.ts'
import { IssueKeyDialog, type Owner } from './IssueKeyForm.tsx'

type Row = { id: string, key_id: string, name: string, scopes: string[], expires_at: string,
  revoked_at: string | null, owner_user_id: string }

type Issued = { keyId: string, pem: string }

/** Revoke, or rotate (a new pair whose private key is handed to `onIssued`); both ask first. */
function useKeyActions(onIssued: (issued: Issued) => void) {
  const queryClient = useQueryClient()
  const { run } = useAction()
  const refresh = () => queryClient.invalidateQueries({ queryKey: keysQuery.queryKey })
  const revoke = async (key: Row) => {
    const ok = await confirm({ title: m.keys_revoke_title({ name: key.name }),
      description: m.keys_revoke_text(), confirmLabel: m.key_revoke(), tone: 'destructive' })
    if (!ok) return
    await run(async () => { await revokeKey(key.id); await refresh() },
      m.keys_revoked_done())
  }
  const rotate = async (key: Row) => {
    const ok = await confirm({ title: m.keys_rotate_title({ name: key.name }),
      description: m.keys_rotate_text(), confirmLabel: m.keys_rotate(), tone: 'destructive' })
    if (!ok) return
    await run(async () => {
      const made = await rotateKey(key.id)
      onIssued({ keyId: made.key.key_id, pem: made.private_key_pem })
      await refresh()
    }, m.keys_rotated())
  }
  return { refresh, revoke, rotate }
}

/** `owners`: who a key may belong to (the page composes it from the users list). */
export function ApiKeysPage({ owners }: { owners: Owner[] }) {
  useDocumentTitle(m.nav_api_keys())
  const keys = useQuery(keysQuery)
  const { dateTime } = useFormat()
  const [issuing, setIssuing] = useState(false)
  const [issued, setIssued] = useState<Issued | null>(null)
  const { refresh, revoke, rotate } = useKeyActions(setIssued)
  const ownerOf = new Map(owners.map((o) => [o.id, o]))
  const columns: Column<Row>[] = [
    { accessorKey: 'name', header: () => m.col_name(),
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
    { id: 'owner', header: () => m.key_owner(), accessorFn: (r) => {
      const o = ownerOf.get(r.owner_user_id)
      return o ? `${o.name} ${o.email}` : ''
    }, cell: ({ row }) => (
      <Person person={ownerOf.get(row.original.owner_user_id)} fallback={m.actor_unknown()} />
    ) },
    { accessorKey: 'key_id', header: () => m.key_id(),
      cell: ({ row }) => <code className="text-xs">{row.original.key_id}</code> },
    { id: 'scopes', accessorFn: (r) => r.scopes.join(' '), header: () => m.key_scopes(),
      cell: ({ row }) => (
        <span className="flex flex-wrap gap-1">
          {row.original.scopes.map((s) => <Badge key={s} tone="outline">{s}</Badge>)}
        </span>
      ) },
    { accessorKey: 'expires_at', header: () => m.key_expires(),
      cell: ({ row }) => dateTime(row.original.expires_at) },
    { accessorKey: 'revoked_at', header: () => m.col_status(), cell: ({ row }) =>
      row.original.revoked_at ? <Badge tone="destructive">{m.key_revoked()}</Badge>
        : <Badge tone="success">{m.keys_active()}</Badge> },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) =>
      row.original.revoked_at ? null : (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => void rotate(row.original)}>
            <RefreshCw />{m.keys_rotate()}
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive"
            onClick={() => void revoke(row.original)}><ShieldOff />{m.key_revoke()}</Button>
        </span>
      ) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<KeyRound />} title={m.keys_title()} description={m.keys_explain()}
        actions={<Button onClick={() => setIssuing(true)}><Plus />{m.key_issue()}</Button>} />
      {keys.error ? <Notice tone="error">{errorText(keys.error)}</Notice> : null}
      <Card>
        <DataTable data={keys.data ?? []} columns={columns} empty={m.keys_empty()}
          loading={keys.isPending} />
      </Card>
      <IssueKeyDialog owners={owners} open={issuing} onOpenChange={setIssuing}
        onIssued={(keyId, pem) => { setIssued({ keyId, pem }); void refresh() }} />
      {issued ? (
        <Modal open onOpenChange={(o) => { if (!o) setIssued(null) }}
          title={m.keys_private_title()} size="lg">
          <div className="flex flex-col gap-3">
            <Notice tone="warn">{m.key_shown_once({ key: issued.keyId })}</Notice>
            <CopyField value={issued.pem} rows={8} label={m.key_private()} />
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
