import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { BookOpenCheck, MessageCircleQuestion, Workflow } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Badge, type BadgeTone } from '../../../components/ui/Badge.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { ALL, Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { Person } from '../../../components/ui/Person.tsx'
import { ViewToggle } from '../../../components/ui/ViewToggle.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { useFormat } from '../../../hooks/useFormat.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Call, callsQuery } from '../api.ts'
import { CallDetail } from './CallDetail.tsx'

type Kind = 'all' | 'run' | 'question'

const STATUS: Record<string, { tone: BadgeTone, text: () => string }> = {
  done: { tone: 'success', text: () => m.res_status_done() },
  failed: { tone: 'destructive', text: () => m.res_status_failed() },
  queued: { tone: 'default', text: () => m.res_status_queued() },
  running: { tone: 'warning', text: () => m.res_status_running() },
  answered: { tone: 'success', text: () => m.res_status_answered() },
  found: { tone: 'primary', text: () => m.res_status_found() },
  no_hits: { tone: 'warning', text: () => m.res_status_no_hits() },
}

function statusBadge(status: string) {
  const s = STATUS[status]
  return <Badge tone={s?.tone ?? 'default'}>{s ? s.text() : status}</Badge>
}

/** `projects`: the ones to filter by; `runBody`: how a run is shown (both composed by the
 * page from other features). */
export function ResultsPage({ projects, runBody }: { projects: { id: string, name: string }[],
  runBody: (id: string) => ReactNode }) {
  useDocumentTitle(m.res_title())
  const { dateTime } = useFormat()
  const [kind, setKind] = useState<Kind>('all')
  const [project, setProject] = useState('')
  const [open, setOpen] = useState<Call | null>(null)
  const calls = useQuery(callsQuery(project || null, kind === 'all' ? null : kind))
  const columns: Column<Call>[] = [
    { accessorKey: 'at', header: () => m.col_when(),
      cell: ({ row }) => <span className="whitespace-nowrap">{dateTime(row.original.at)}</span> },
    { id: 'who', header: () => m.res_who(),
      accessorFn: (c) => c.actor ? `${c.actor.name} ${c.actor.email}` : '',
      cell: ({ row }) => (
        <Person person={row.original.actor} fallback={m.res_someone()} />) },
    { accessorKey: 'title', header: () => m.res_what(), cell: ({ row }) => (
      <span className="flex min-w-0 items-center gap-2">
        {row.original.kind === 'run'
          ? <Workflow className="size-4 shrink-0 text-primary" />
          : <MessageCircleQuestion className="size-4 shrink-0 text-primary" />}
        <span className="line-clamp-2 max-w-md">{row.original.title}</span>
      </span>
    ) },
    { accessorKey: 'channel', header: () => m.res_channel(),
      cell: ({ row }) => <Badge tone="outline">{row.original.channel}</Badge> },
    { accessorKey: 'project', header: () => m.res_project() },
    { accessorKey: 'status', header: () => m.res_result(),
      cell: ({ row }) => statusBadge(row.original.status) },
  ]
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<BookOpenCheck />} title={m.res_title()} description={m.res_intro()} />
      {calls.error ? <Notice tone="error">{errorText(calls.error)}</Notice> : null}
      <Card>
        <DataTable data={calls.data ?? []} columns={columns} empty={m.dash_no_data()}
          loading={calls.isPending} onRowClick={setOpen} pageSize={20} toolbar={(
            <>
              <Select aria-label={m.res_project()} className="w-48" value={project || ALL}
                onChange={(v) => setProject(v === ALL ? '' : v)} options={[
                  { value: ALL, label: m.dash_all_projects() },
                  ...projects.map((p) => ({ value: p.id, label: p.name })),
                ]} />
              <ViewToggle value={kind} onChange={setKind} options={[
                { value: 'all', label: m.res_all(), icon: <BookOpenCheck /> },
                { value: 'run', label: m.res_runs(), icon: <Workflow /> },
                { value: 'question', label: m.res_questions(), icon: <MessageCircleQuestion /> },
              ]} />
            </>
          )} />
      </Card>
      {open ? (
        <CallDetail call={open} onClose={() => setOpen(null)} runBody={runBody}
          footer={open.kind === 'run' ? (
          <Link to="/projects/$projectId" params={{ projectId: open.project_id }}
            search={{ tab: 'runs', run: open.id }}
            className="text-sm font-medium text-primary hover:underline">
            {m.res_open_run()}
          </Link>
        ) : null} />
      ) : null}
    </div>
  )
}
