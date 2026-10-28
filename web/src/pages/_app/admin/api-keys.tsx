// Composes two features: the users list (owners) feeds the API keys page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { usersQuery } from '../../../features/admin/api.ts'
import { ApiKeysPage } from '../../../features/apikeys/components/ApiKeysPage.tsx'

function Keys() {
  const users = useQuery(usersQuery)
  const owners = (users.data ?? []).map((u) => ({ id: u.id, email: u.email,
    name: u.display_name, avatar: u.avatar }))
  return <ApiKeysPage owners={owners} />
}

export const Route = createFileRoute('/_app/admin/api-keys')({ component: Keys })
