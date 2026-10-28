import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../../testing/render.tsx'
import { EventsPanel } from './components/EventsPanel.tsx'

describe('events panel', () => {
  it('creates a receiver, shows its secret once and links events to their page', async () => {
    renderApp(<EventsPanel projectId="p1" />)
    expect(await screen.findByRole('link', { name: 'runs/r1' }))
      .toHaveAttribute('href', '/projects/p1?tab=runs&run=r1')
    fireEvent.click(screen.getByRole('button', { name: 'New receiver' }))
    const form = await screen.findByRole('dialog')
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'z' } })
    fireEvent.change(within(form).getByLabelText(/receiver url/i),
      { target: { value: 'https://x.test/h' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Receiver added')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('whsec_TEST')).toBeInTheDocument()
  })
})
