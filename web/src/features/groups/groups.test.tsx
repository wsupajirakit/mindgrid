import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { GroupsPage } from './components/GroupsPage.tsx'
import { pickOption } from '../../testing/select.ts'

const PEOPLE = [{ id: 'u2', name: 'User 2', email: 'user2@example.com' },
  { id: 'u3', name: 'User 3', email: 'user3@example.com' }]

describe('groups page', () => {
  it('creates a group and adds a person to one', async () => {
    renderApp(<GroupsPage people={PEOPLE} />)
    expect(await screen.findByText('Analysts')).toBeInTheDocument()
    expect(screen.getByText('2 members')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'New group' }))
    const form = await screen.findByRole('dialog')
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Ops' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Create' }))
    expect(await screen.findByText('Group created')).toBeInTheDocument()
    expect(writes[0]).toEqual(['POST', 'admin/groups', { name: 'Ops', description: '' }])
    const row = screen.getByText('Research team').closest('tr') as HTMLElement
    fireEvent.click(within(row).getByRole('button', { name: 'Members' }))
    const members = await screen.findByRole('dialog')
    expect(await within(members).findByText('user2@example.com')).toBeInTheDocument()
    await pickOption(within(members).getByLabelText('Add a person'), /User 3/)
    fireEvent.click(within(members).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Added to the group')).toBeInTheDocument()
    expect(writes[1]?.slice(0, 2)).toEqual(['PUT', 'admin/groups/g1/members/u3'])
  })
})
