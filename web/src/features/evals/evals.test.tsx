import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../../testing/render.tsx'
import { EvalsPanel } from './components/EvalsPanel.tsx'

describe('evals panel', () => {
  it('lists runs with their scores and opens one with its judgement and cases', async () => {
    renderApp(<EvalsPanel projectId="p1" />)
    expect(await screen.findByText('0.75')).toBeInTheDocument()
    expect(screen.getByText('local:judge')).toBeInTheDocument()
    fireEvent.click(screen.getByText('basics'))
    const detail = await screen.findByRole('dialog')
    expect(within(detail).getByText('judge_context 0.50')).toBeInTheDocument()
    expect(within(detail).getByText('judged by local:judge · answers by —'))
      .toBeInTheDocument()
    expect(within(detail).getByText('stops?')).toBeInTheDocument()
    expect(within(detail).getAllByText('pass')).toHaveLength(2)
  })
})
