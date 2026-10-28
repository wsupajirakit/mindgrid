import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { MembersPanel } from './components/MembersPanel.tsx'
import { pickOption } from '../../testing/select.ts'

describe('members panel', () => {
  it('shows where each role comes from and gives a group a role', async () => {
    renderApp(<MembersPanel projectId="p1" groups={[{ id: 'g1', name: 'Analysts' }]} />)
    expect(await screen.findByText('bob@example.com')).toBeInTheDocument()
    expect(screen.getByText('Analysts · Viewer')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Add group' }))
    const form = await screen.findByRole('dialog')
    await pickOption(within(form).getByLabelText('Groups'), 'Analysts')
    await pickOption(within(form).getByLabelText('Role'), 'Analyst')
    fireEvent.click(within(form).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Group added')).toBeInTheDocument()
    expect(writes[0]).toEqual(['PUT', 'projects/p1/groups/g1', { role: 'analyst' }])
  })

  it("sets a person's own role over their group's", async () => {
    renderApp(<MembersPanel projectId="p1" groups={[]} />)
    await screen.findByText('bob@example.com')
    const own = screen.getAllByRole('combobox', { name: 'Own role (wins)' })[0] as HTMLElement
    await pickOption(own, 'Editor')
    expect((await screen.findAllByText('Role changed')).length).toBeGreaterThan(0)
    expect(writes[0]).toEqual(['PUT', 'projects/p1/members/u2', { role: 'editor' }])
  })
})
