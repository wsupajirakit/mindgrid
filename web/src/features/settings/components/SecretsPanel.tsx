import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Field, Input } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { putSecret, removeSecret, secretsQuery } from '../api.ts'

type Row = { name: string, hint: string, updated_at: string }

/** Write-only: the value is sent once and never shown again (only a short hint). */
export function SecretsPanel({ projectId }: { projectId: string }) {
  const secrets = useQuery(secretsQuery(projectId))
  const queryClient = useQueryClient()
  const { dateTime } = useFormat()
  const { busy, run } = useAction()
  const [editing, setEditing] = useState<{ name: string, fixed: boolean } | null>(null)
  const [value, setValue] = useState('')
  const refresh = () => queryClient.invalidateQueries({
    queryKey: secretsQuery(projectId).queryKey })
  const save = async () => {
    if (!editing) return
    const ok = await run(async () => {
      await putSecret(projectId, editing.name, value)
      await refresh()
    },
      m.sec_saved())
    if (ok) { setEditing(null); setValue('') }
  }
  const remove = async (name: string) => {
    const ok = await confirm({ title: m.sec_remove_title({ name }),
      description: m.sec_remove_text(),
      confirmLabel: m.action_remove(), tone: 'destructive' })
    if (!ok) return
    await run(async () => { await removeSecret(projectId, name); await refresh() },
      m.sec_removed())
  }
  const columns: Column<Row>[] = [
    { accessorKey: 'name', header: () => m.col_name(),
      cell: ({ row }) => <code className="text-xs">{row.original.name}</code> },
    { accessorKey: 'hint', header: () => m.col_hint(),
      cell: ({ row }) => (
        <code className="text-xs text-muted-foreground">{row.original.hint}</code>
      ) },
    { accessorKey: 'updated_at', header: () => m.col_updated(),
      cell: ({ row }) => dateTime(row.original.updated_at) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end gap-1">
        <Button variant="ghost" size="sm"
          onClick={() => setEditing({ name: row.original.name, fixed: true })}>
            {m.sec_replace()}
          </Button>
        <Button variant="ghost" size="sm" className="text-destructive"
          onClick={() => void remove(row.original.name)}><Trash2 />{m.action_remove()}</Button>
      </span>
    ) },
  ]
  return (
    <div className="flex flex-col gap-4">
      <Notice>{m.secrets_write_only()}</Notice>
      {secrets.error ? <Notice tone="error">{errorText(secrets.error)}</Notice> : null}
      <DataTable data={secrets.data ?? []} columns={columns} empty={m.secrets_empty()}
        loading={secrets.isPending} toolbar={(
          <Button onClick={() => setEditing({ name: '', fixed: false })}>
            <Plus />{m.sec_new()}
          </Button>
        )} />
      <FormModal open={editing !== null} onOpenChange={(o) => { if (!o) setEditing(null) }}
        title={editing?.fixed ? editing.name : m.sec_new()} submitLabel={m.action_save()}
        busy={busy} disabled={!editing?.name || !value} onSubmit={save}>
        {editing?.fixed ? null : (
          <Field label={m.col_name()}>
            <Input value={editing?.name ?? ''} autoFocus
              onChange={(e) => setEditing({ name: e.target.value, fixed: false })} />
          </Field>
        )}
        <Field label={m.secret_value()}>
          <Input type="password" autoComplete="off" value={value}
            onChange={(e) => setValue(e.target.value)} />
        </Field>
      </FormModal>
    </div>
  )
}
