// Composes the groups list (what a person may join) with the users page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { UsersPage } from '../../../features/admin/components/UsersPage.tsx'
import { groupsQuery } from '../../../features/groups/api.ts'

function Page() {
  const groups = useQuery(groupsQuery)
  return <UsersPage groups={(groups.data ?? []).map((g) => ({ id: g.id, name: g.name }))} />
}

export const Route = createFileRoute('/_app/admin/users')({ component: Page })
