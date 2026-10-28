import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider,
} from '@tanstack/react-router'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { holdSignIn } from '../../testing/mocks/testServer.ts'
import { SignInPage } from './components/SignInPage.tsx'

function renderSignIn() {
  const root = createRootRoute()
  const login = createRoute({ getParentRoute: () => root, path: '/login', component: SignInPage })
  const dashboard = createRoute({ getParentRoute: () => root, path: '/dashboard',
    component: () => <p>{'dashboard-page'}</p> })
  const router = createRouter({ routeTree: root.addChildren([login, dashboard]),
    history: createMemoryHistory({ initialEntries: ['/login'] }) })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

async function submit(password: string) {
  fireEvent.change(await screen.findByLabelText(/email/i), { target: { value: 'a@example.com' } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } })
  fireEvent.click(screen.getByRole('button'))
}

describe('sign-in page', () => {
  it('shows the brand from the server and the translated failure', async () => {
    renderSignIn()
    expect(await screen.findByRole('heading', { name: /Test Brand/ })).toBeInTheDocument()
    await submit('wrong password')
    expect(await screen.findByRole('alert')).toHaveTextContent(/wrong|password/i)
  })

  it('goes to the dashboard after signing in', async () => {
    renderSignIn()
    await submit('correct horse battery staple')
    expect(await screen.findByText('dashboard-page')).toBeInTheDocument()
  })

  it('shows it is working while the server answers, and says so when that is slow', async () => {
    const answer = holdSignIn()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      renderSignIn()
      await submit('correct horse battery staple')
      const button = await screen.findByRole('button', { name: /signing in/i })
      expect(button).toHaveAttribute('aria-busy', 'true')
      expect(screen.getByLabelText(/email/i)).toBeDisabled()
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
      expect(screen.queryByRole('status')).toBeNull()
      act(() => { vi.advanceTimersByTime(4000) })
      expect(screen.getByRole('status')).toHaveTextContent(/longer than usual/i)
      answer()
      expect(await screen.findByText('dashboard-page')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
