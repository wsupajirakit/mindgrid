import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Proposal } from './api.ts'
import { ProposalView } from './components/ProposalView.tsx'

const proposal = {
  id: 'pr1', source_id: 's1', project_id: 'p1', from_commit: 'aaaaaaaaaaaa',
  to_commit: 'bbbbbbbbbbbb', status: 'pending', redactions: 3, created_at: '2026-10-25T00:00:00Z',
  items: [
    { kind: 'knowledge_update', path: 'skills/a/SKILL.md', summary: 'rules (M)',
      decision: 'pending', detail: { diff: '+ Stops sit 2 ATR under entry.' } },
    { kind: 'measure', path: 'skills/a/refs.md', summary: 'won 62% of trades',
      decision: 'rejected', detail: {} },
  ],
} as unknown as Proposal

describe('synapse proposal', () => {
  it('lists items with their decision, shows the sanitised change and the task list', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ProposalView proposal={proposal} />
      </QueryClientProvider>,
    )
    expect(screen.getByText('skills/a/SKILL.md')).toBeInTheDocument()
    expect(screen.getByText('rejected')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Accept' })).toHaveLength(1)
    fireEvent.click(screen.getAllByRole('button', { name: 'Show' })[0] as HTMLElement)
    expect(screen.getByText('+ Stops sit 2 ATR under entry.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /accepted tasks/i }))
      .toHaveAttribute('href', expect.stringContaining('synapse/proposals/pr1/tasks.md'))
  })
})
