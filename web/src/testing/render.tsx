// Renders a component the way the app shell does: a fresh query cache, a router (so links
// work) and the toast, confirmation and tooltip hosts, so tests can follow a change through
// to its toast.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory, createRootRoute, createRouter, RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { LocaleRoot } from '../app/LocaleRoot.tsx'
import { ConfirmHost } from '../components/ui/Confirm.tsx'
import { Toaster } from '../components/ui/Toast.tsx'
import { TooltipProvider } from '../components/ui/Tooltip.tsx'

export function renderApp(ui: ReactNode, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const root = createRootRoute({ component: () => (
    <TooltipProvider>
      {ui}
      <Toaster />
      <ConfirmHost />
    </TooltipProvider>
  ) })
  const router = createRouter({ routeTree: root,
    history: createMemoryHistory({ initialEntries: [path] }) })
  return render(
    <QueryClientProvider client={client}>
      <LocaleRoot><RouterProvider router={router} /></LocaleRoot>
    </QueryClientProvider>,
  )
}
