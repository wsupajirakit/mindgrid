// Composes the projects and categories (targets for accepted knowledge) with Synapse.
import { useQueries, useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { categoriesQuery } from '../../../features/categories/api.ts'
import { projectsQuery } from '../../../features/projects/api.ts'
import { SynapsePage } from '../../../features/synapse/components/SynapsePage.tsx'

function Synapse() {
  const { proposal } = Route.useSearch()
  const projects = useQuery(projectsQuery())
  const cats = useQueries({ queries: (projects.data ?? []).map((p) => categoriesQuery(p.id)) })
  const targets = (projects.data ?? []).flatMap((p, i) => (cats[i]?.data ?? []).map((c) => ({
    projectId: p.id, categoryId: c.id, label: `${p.name} / ${c.name}` })))
  return <SynapsePage targets={targets} openProposal={proposal} />
}

export const Route = createFileRoute('/_app/admin/synapse')({
  component: Synapse,
  validateSearch: (s: Record<string, unknown>): { proposal?: string } => ({
    proposal: typeof s.proposal === 'string' && s.proposal ? s.proposal : undefined,
  }),
})
