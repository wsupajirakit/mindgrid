import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  BookText, Cable, Database, FlaskConical, FolderTree, KeyRound, MessageCircleQuestion, Play,
  Radio, ScrollText, Settings, Trash2, Users, Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { confirm } from '../../../components/ui/Confirm.tsx'
import { Cover } from '../../../components/ui/Cover.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { Tabs } from '../../../components/ui/Tabs.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { deleteProject, projectQuery } from '../api.ts'
import { CopyProjectButton } from './CopyProjectDialog.tsx'

export type Panels = { knowledge: ReactNode, ask: ReactNode, playbooks: ReactNode,
  runs: ReactNode, data: ReactNode, connectors: ReactNode, events: ReactNode, evals: ReactNode,
  categories: ReactNode, members: ReactNode, settings: ReactNode, secrets: ReactNode,
  audit: ReactNode }

/** One project; each tab is a panel from another feature, composed by the page. */
/** `superadmin` adds the copy-to-another-project action. */
export function ProjectPage({ projectId, panels, tab, onTab, superadmin = false }: {
  projectId: string, tab?: string, onTab: (tab: string) => void, panels: Panels,
  superadmin?: boolean }) {
  const project = useQuery(projectQuery(projectId))
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { run } = useAction()
  useDocumentTitle(project.data?.name ?? '')
  if (project.error) return <Notice tone="error">{errorText(project.error)}</Notice>
  if (!project.data) return <Skeleton className="h-40 rounded-xl" />
  const name = project.data.name
  const remove = async () => {
    const ok = await confirm({ title: m.project_delete_title({ name }),
      description: m.project_delete_text(), confirmLabel: m.project_delete(),
      tone: 'destructive' })
    if (!ok) return
    const done = await run(async () => {
      await deleteProject(projectId)
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
    }, m.project_deleted())
    if (done) await navigate({ to: '/projects' })
  }
  const groups = [
    { label: m.tabgroup_analysis(), items: [
      { value: 'playbooks', label: m.tab_playbooks(), icon: <Workflow />,
        content: panels.playbooks },
      { value: 'runs', label: m.tab_runs(), icon: <Play />, content: panels.runs },
      { value: 'data', label: m.tab_data(), icon: <Database />, content: panels.data },
      { value: 'connectors', label: m.tab_connectors(), icon: <Cable />,
        content: panels.connectors },
    ] },
    { label: m.tabgroup_knowledge_optional(), items: [
      { value: 'knowledge', label: m.tab_knowledge(), icon: <BookText />,
        content: panels.knowledge },
      { value: 'categories', label: m.tab_categories(), icon: <FolderTree />,
        content: panels.categories },
    ] },
    { label: m.tabgroup_ask(), items: [
      { value: 'ask', label: m.tab_ask(), icon: <MessageCircleQuestion />, content: panels.ask },
      { value: 'evals', label: m.tab_evals(), icon: <FlaskConical />, content: panels.evals },
    ] },
    { label: m.tabgroup_manage(), items: [
      { value: 'members', label: m.tab_members(), icon: <Users />, content: panels.members },
      { value: 'events', label: m.tab_events(), icon: <Radio />, content: panels.events },
      { value: 'settings', label: m.tab_settings(), icon: <Settings />,
        content: panels.settings },
      { value: 'secrets', label: m.tab_secrets(), icon: <KeyRound />, content: panels.secrets },
      { value: 'audit', label: m.tab_audit(), icon: <ScrollText />, content: panels.audit },
    ] },
  ]
  return (
    <div className="flex flex-col gap-6">
      <Cover seed={projectId} className="h-36 rounded-xl shadow-card">
        <div className="flex h-full flex-wrap items-end gap-3 bg-gradient-to-t from-black/50
          to-transparent p-5">
          <div className="min-w-0 flex-1 text-white">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{name}</h1>
            <p className="line-clamp-1 text-sm text-white/80">
              {project.data.description || project.data.slug}
            </p>
          </div>
          {superadmin ? <CopyProjectButton projectId={projectId} /> : null}
          <Button variant="secondary" size="sm" onClick={() => void remove()}>
            <Trash2 />{m.project_delete()}
          </Button>
        </div>
      </Cover>
      <Tabs defaultValue="playbooks" value={tab ?? 'playbooks'} onValueChange={onTab}
        groups={groups} label={m.project_sections()} />
    </div>
  )
}
