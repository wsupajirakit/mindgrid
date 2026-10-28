import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowRight, FolderKanban, LayoutGrid, Plus, Table2 } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { Cover } from '../../../components/ui/Cover.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { matches, SearchBox } from '../../../components/ui/SearchBox.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { ViewToggle } from '../../../components/ui/ViewToggle.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { projectsQuery } from '../api.ts'
import { NewProjectDialog } from './NewProjectForm.tsx'

type Row = { id: string, slug: string, name: string, description: string }

const columns = (): Column<Row>[] => [
  { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
    <Link to="/projects/$projectId" params={{ projectId: row.original.id }}
      className="font-medium text-primary hover:underline">{row.original.name}</Link>
  ) },
  { accessorKey: 'slug', header: () => m.col_slug(),
    cell: ({ row }) => <code className="text-xs">{row.original.slug}</code> },
  { accessorKey: 'description', header: () => m.col_description(), enableSorting: false },
]

function ProjectCard({ project }: { project: Row }) {
  return (
    <Link to="/projects/$projectId" params={{ projectId: project.id }}
      className="group overflow-hidden rounded-xl border border-border bg-card shadow-card
        transition hover:-translate-y-0.5 hover:shadow-lg">
      <Cover seed={project.id} className="h-24">
        <div className="flex h-full items-end p-3">
          <span className="grid size-9 place-items-center rounded-lg bg-white/20 text-white
            backdrop-blur"><FolderKanban className="size-4" /></span>
        </div>
      </Cover>
      <div className="flex flex-col gap-1 p-4">
        <div className="flex items-center gap-2">
          <h3 className="truncate font-semibold">{project.name}</h3>
          <ArrowRight className="ml-auto size-4 text-muted-foreground transition
            group-hover:translate-x-0.5 group-hover:text-foreground" />
        </div>
        <code className="text-xs text-muted-foreground">{project.slug}</code>
        <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">
          {project.description || '—'}
        </p>
      </div>
    </Link>
  )
}

/** `startNew` shows the new-project form (a link elsewhere asked for it); `onStarted` is
 * told when that form closes, so the request is not repeated. */
export function ProjectsPage({ startNew = false, onStarted }: { startNew?: boolean,
  onStarted?: () => void }) {
  useDocumentTitle(m.nav_projects())
  const projects = useQuery(projectsQuery())
  const [view, setView] = useState<'cards' | 'table'>('cards')
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const setOpen = (open: boolean) => {
    setCreating(open)
    if (!open && startNew) onStarted?.()
  }
  const all = projects.data ?? []
  const shown = all.filter((p) => matches(query, p.name, p.slug, p.description))
  const newButton = (
    <Button onClick={() => setCreating(true)}><Plus />{m.projects_new()}</Button>
  )
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<FolderKanban />} title={m.projects_title()}
        description={m.projects_intro()} actions={newButton} />
      {projects.error ? <Notice tone="error">{errorText(projects.error)}</Notice> : null}
      <div className="flex flex-wrap items-center gap-2">
        {view === 'cards' ? (
          <SearchBox value={query} onChange={setQuery} />
        ) : null}
        <div className="ml-auto">
          <ViewToggle value={view} onChange={setView} options={[
            { value: 'cards', label: m.view_cards(), icon: <LayoutGrid /> },
            { value: 'table', label: m.view_table(), icon: <Table2 /> },
          ]} />
        </div>
      </div>
      {view === 'table' ? (
        <Card><DataTable data={all} columns={columns()} empty={m.projects_empty()}
          loading={projects.isPending} /></Card>
      ) : projects.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-52 rounded-xl" />)}
        </div>
      ) : shown.length === 0 ? (
        <Card><EmptyState text={all.length === 0 ? m.projects_empty() : m.ui_no_results()}
          action={all.length === 0 ? newButton : undefined} /></Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((p) => <ProjectCard key={p.id} project={p} />)}
        </div>
      )}
      <NewProjectDialog open={creating || startNew} onOpenChange={setOpen} />
    </div>
  )
}
