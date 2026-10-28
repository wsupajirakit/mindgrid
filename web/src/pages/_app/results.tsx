// Composes the projects list (filter choices) and the run view with the results page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { ResultsPage } from '../../features/insights/components/ResultsPage.tsx'
import { RunById } from '../../features/playbooks/components/RunDetail.tsx'
import { projectsQuery } from '../../features/projects/api.ts'

function Page() {
  const projects = useQuery(projectsQuery())
  return <ResultsPage projects={projects.data ?? []} runBody={(id) => <RunById id={id} />} />
}

export const Route = createFileRoute('/_app/results')({ component: Page })
