// Composes the signed-in account (superadmin controls) with the playbooks page.
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { meQuery } from '../../features/auth/api.ts'
import { PlaybooksPage } from '../../features/playbooks/components/PlaybooksPage.tsx'

function Page() {
  const me = useQuery(meQuery)
  return <PlaybooksPage superadmin={me.data?.system_role === 'superadmin'} />
}

export const Route = createFileRoute('/_app/playbooks')({ component: Page })
