import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, GitBranch, Plus, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Proposal, proposalsQuery, type Source, sourcesQuery } from '../api.ts'
import { ProposalView } from './ProposalView.tsx'
import { CheckDialog, SourceDialog, type Target } from './SourceDialog.tsx'

function Sources({ targets }: { targets: Target[] }) {
  const sources = useQuery(sourcesQuery)
  const [adding, setAdding] = useState(false)
  const [checking, setChecking] = useState<Source | null>(null)
  const columns: Column<Source>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex items-center gap-2 font-medium">
        <GitBranch className="size-4 text-primary" />{row.original.name}
      </span>
    ) },
    { accessorKey: 'last_commit', header: () => m.syn_last_commit(), cell: ({ row }) => (
      <span className="flex flex-col gap-1">
        <code className="text-xs">{row.original.last_commit.slice(0, 10) || m.conn_never()}</code>
        {row.original.last_error ? (
          <span className="text-xs text-destructive">{row.original.last_error}</span>
        ) : null}
      </span>
    ) },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) => (
      <span className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => setChecking(row.original)}>
          <RefreshCw />{m.syn_check()}
        </Button>
      </span>
    ) },
  ]
  return (
    <Card title={m.syn_sources()} description={m.syn_intro()} actions={(
      <Button size="sm" onClick={() => setAdding(true)}><Plus />{m.syn_new()}</Button>
    )}>
      {sources.error ? <Notice tone="error">{errorText(sources.error)}</Notice> : null}
      <DataTable data={sources.data ?? []} columns={columns} empty={m.syn_no_sources()}
        loading={sources.isPending} />
      <SourceDialog targets={targets} open={adding} onOpenChange={setAdding} />
      {checking ? <CheckDialog source={checking} onClose={() => setChecking(null)} /> : null}
    </Card>
  )
}

/** Learning from source repositories: sources, and proposals to review item by item. */
export function SynapsePage({ targets, openProposal }: { targets: Target[],
  openProposal?: string }) {
  useDocumentTitle(m.syn_title())
  const proposals = useQuery(proposalsQuery)
  const { dateTime } = useFormat()
  const [open, setOpen] = useState(openProposal ?? '')
  const picked = proposals.data?.find((p) => p.id === open)
  const columns: Column<Proposal>[] = [
    { accessorKey: 'created_at', header: () => m.col_when(),
      cell: ({ row }) => dateTime(row.original.created_at) },
    { accessorKey: 'status', header: () => m.col_status(),
      cell: ({ row }) => <Badge tone="primary">{row.original.status}</Badge> },
    { id: 'items', accessorFn: (p) => p.items.length, header: () => m.syn_items(),
      cell: ({ row }) => m.syn_item_count({ n: String(row.original.items.length) }) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<BrainCircuit />} title={m.syn_title()} description={m.syn_intro()} />
      <Sources targets={targets} />
      <Card title={m.syn_proposals()}>
        {proposals.error ? <Notice tone="error">{errorText(proposals.error)}</Notice> : null}
        <DataTable data={proposals.data ?? []} columns={columns} empty={m.syn_no_proposals()}
          loading={proposals.isPending} onRowClick={(p) => setOpen(p.id)} />
      </Card>
      {picked ? (
        <Modal open onOpenChange={(o) => { if (!o) setOpen('') }} size="xl"
          title={m.syn_proposal_title({ when: dateTime(picked.created_at) })}>
          <ProposalView proposal={picked} />
        </Modal>
      ) : null}
    </div>
  )
}
