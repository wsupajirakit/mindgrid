import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { LocaleRoot } from './app/LocaleRoot.tsx'
import { makeQueryClient } from './app/queryClient.ts'
import { makeRouter } from './app/router.tsx'
import { onSignedOut } from './services/api/client.ts'
import './styles/index.css'

const queryClient = makeQueryClient()
const router = makeRouter(queryClient)
// A 401 anywhere means the session ended: go to sign-in (keeping no cached data).
onSignedOut(() => {
  if (router.state.location.pathname === '/login') return
  queryClient.clear()
  void router.navigate({ to: '/login' })
})

const root = document.getElementById('root')
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <LocaleRoot><RouterProvider router={router} /></LocaleRoot>
      </QueryClientProvider>
    </StrictMode>,
  )
}
