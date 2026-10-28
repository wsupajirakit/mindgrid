// Everything behind sign-in: no session -> /login (the API is the authority; this only
// avoids rendering a page that cannot load).
import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { meQuery } from '../features/auth/api.ts'
import { AppShell } from '../layouts/AppShell.tsx'

export const Route = createFileRoute('/_app')({
  beforeLoad: async ({ context }) => {
    try {
      return { me: await context.queryClient.ensureQueryData(meQuery) }
    } catch {
      throw redirect({ to: '/login' })
    }
  },
  component: () => <AppShell><Outlet /></AppShell>,
})
