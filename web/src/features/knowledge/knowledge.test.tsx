import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AskPanel } from './components/AskPanel.tsx'

describe('ask panel', () => {
  it('shows the Context Pack passages with their trust tag and skipped retrievers', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AskPanel projectId="p1" />
      </QueryClientProvider>,
    )
    fireEvent.change(screen.getByLabelText(/question/i), { target: { value: 'yields?' } })
    fireEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(await screen.findByText('Treasury yields rose.')).toBeInTheDocument()
    expect(screen.getByText('P1')).toBeInTheDocument()
    expect(screen.getByText('Claimed')).toBeInTheDocument()
    expect(screen.getByText(/meaning search skipped/i)).toBeInTheDocument()
    expect(screen.getByText('relevance 0.91')).toBeInTheDocument()
    expect(screen.getByText(/2 unrelated passage/)).toBeInTheDocument()
  })
})
