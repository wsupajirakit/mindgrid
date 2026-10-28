// The project page composes panels from several features (pages may; features may not).
// `?tab=` opens a tab and `run` / `document` / `dataset` open an item: event links use them.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Card } from '../../../components/ui/Card.tsx'
import { AuditLog } from '../../../features/audit/components/AuditLog.tsx'
import { meQuery } from '../../../features/auth/api.ts'
import { CategoriesPanel } from '../../../features/categories/components/CategoriesPanel.tsx'
import {
  NewCategoryButton,
} from '../../../features/categories/components/NewCategoryDialog.tsx'
import { ConnectorsPanel } from '../../../features/data/components/ConnectorsPanel.tsx'
import { DataPanel } from '../../../features/data/components/DataPanel.tsx'
import { EvalsPanel } from '../../../features/evals/components/EvalsPanel.tsx'
import { EventsPanel } from '../../../features/events/components/EventsPanel.tsx'
import { groupsQuery } from '../../../features/groups/api.ts'
import { AskPanel } from '../../../features/knowledge/components/AskPanel.tsx'
import { DocumentsPanel } from '../../../features/knowledge/components/DocumentsPanel.tsx'
import { MembersPanel } from '../../../features/members/components/MembersPanel.tsx'
import { PlaybooksPanel } from '../../../features/playbooks/components/PlaybooksPanel.tsx'
import { RunsPanel } from '../../../features/playbooks/components/RunsPanel.tsx'
import { projectQuery } from '../../../features/projects/api.ts'
import { ProjectPage } from '../../../features/projects/components/ProjectPage.tsx'
import { SecretsPanel } from '../../../features/settings/components/SecretsPanel.tsx'
import { SettingsPanel } from '../../../features/settings/components/SettingsPanel.tsx'

import { m } from '../../../paraglide/messages.js'

type Search = { tab?: string, run?: string, document?: string, dataset?: string }
const text = (v: unknown) => (typeof v === 'string' && v ? v : undefined)

function Project() {
  const { projectId } = Route.useParams()
  const me = useQuery(meQuery)
  const project = useQuery(projectQuery(projectId))
  const groups = useQuery(groupsQuery)
  const groupChoices = (groups.data ?? []).map((g) => ({ id: g.id, name: g.name }))
  const canManage = project.data?.can_manage === true
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  return (
    <ProjectPage projectId={projectId} tab={search.tab}
      superadmin={me.data?.system_role === 'superadmin'}
      onTab={(tab) => void navigate({ search: { tab } })} panels={{
        knowledge: (
          <Card title={m.tab_knowledge()} description={m.knowledge_intro()}>
            <DocumentsPanel projectId={projectId} initialDocument={search.document}
              newCategory={<NewCategoryButton projectId={projectId} />} />
          </Card>
        ),
        ask: <AskPanel projectId={projectId} />,
        evals: <EvalsPanel projectId={projectId} />,
        playbooks: <PlaybooksPanel projectId={projectId} canManage={canManage} />,
        runs: <RunsPanel projectId={projectId} initialRun={search.run} />,
        data: <DataPanel projectId={projectId} initialDataset={search.dataset} />,
        connectors: <ConnectorsPanel projectId={projectId} />,
        events: <EventsPanel projectId={projectId} />,
        categories: (
          <Card title={m.tab_categories()} description={m.categories_intro()}>
            <CategoriesPanel projectId={projectId} groups={groupChoices} />
          </Card>
        ),
        members: <MembersPanel projectId={projectId} groups={groupChoices} />,
        settings: (
          <Card title={m.tab_settings()} description={m.project_settings_intro()}>
            <SettingsPanel scope={{ kind: 'project', id: projectId }} />
          </Card>
        ),
        secrets: (
          <Card title={m.tab_secrets()} description={m.secrets_intro()}>
            <SecretsPanel projectId={projectId} />
          </Card>
        ),
        audit: (
          <Card title={m.tab_audit()} description={m.logs_intro()}>
            <AuditLog projectId={projectId} />
          </Card>
        ),
      }} />
  )
}

export const Route = createFileRoute('/_app/projects/$projectId')({
  component: Project,
  validateSearch: (s: Record<string, unknown>): Search => ({
    tab: text(s.tab), run: text(s.run), document: text(s.document), dataset: text(s.dataset),
  }),
})
