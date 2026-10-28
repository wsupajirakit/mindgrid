import type { QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'
import { PageLoader } from '../components/ui/PageLoader.tsx'
import { routeTree } from './routeTree.gen.ts'

export type RouterContext = { queryClient: QueryClient }

export function makeRouter(queryClient: QueryClient) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    scrollRestoration: true,
    // A slow page shows the loader instead of a blank screen; a fast one never flashes it.
    defaultPendingComponent: PageLoader,
    defaultPendingMs: 300,
    defaultPendingMinMs: 400,
  })
}

declare module '@tanstack/react-router' {
  interface Register { router: ReturnType<typeof makeRouter> }
}
