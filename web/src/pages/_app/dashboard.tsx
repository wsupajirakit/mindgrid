// Composes the projects list (filter choices) with the dashboard page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { DashboardPage } from '../../features/insights/components/DashboardPage.tsx'
import { projectsQuery } from '../../features/projects/api.ts'

function Page() {
  const projects = useQuery(projectsQuery())
  return <DashboardPage projects={projects.data ?? []} />
}

export const Route = createFileRoute('/_app/dashboard')({ component: Page })
