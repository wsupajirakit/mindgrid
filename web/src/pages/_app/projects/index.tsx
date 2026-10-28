import { createFileRoute } from '@tanstack/react-router'
import { ProjectsPage } from '../../../features/projects/components/ProjectsPage.tsx'

function Page() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return <ProjectsPage startNew={search.new === true}
    onStarted={() => void navigate({ search: {}, replace: true })} />
}

export const Route = createFileRoute('/_app/projects/')({
  component: Page,
  validateSearch: (s: Record<string, unknown>): { new?: boolean } => ({
    new: s.new === true || s.new === 'true' || s.new === 1 ? true : undefined,
  }),
})
