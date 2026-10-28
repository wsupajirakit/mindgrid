import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import type { RouterContext } from '../app/router.tsx'
import { RouteProgress } from '../layouts/RouteProgress.tsx'

function Root() {
  return (
    <>
      <RouteProgress />
      <Outlet />
    </>
  )
}

export const Route = createRootRouteWithContext<RouterContext>()({ component: Root })
