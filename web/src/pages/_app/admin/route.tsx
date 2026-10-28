// Superadmin pages: others are sent back (the API refuses them anyway).
import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/admin')({
  beforeLoad: ({ context }) => {
    if (context.me.system_role !== 'superadmin') throw redirect({ to: '/projects' })
  },
  component: Outlet,
})
