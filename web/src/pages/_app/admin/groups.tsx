// Composes the users list (who may join a group) with the groups page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { usersQuery } from '../../../features/admin/api.ts'
import { GroupsPage } from '../../../features/groups/components/GroupsPage.tsx'

function Page() {
  const users = useQuery(usersQuery)
  const people = (users.data ?? []).map((u) => ({ id: u.id, name: u.display_name,
    email: u.email, avatar: u.avatar }))
  return <GroupsPage people={people} />
}

export const Route = createFileRoute('/_app/admin/groups')({ component: Page })
