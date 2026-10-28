import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { UsersPage } from './components/UsersPage.tsx'

describe('users page', () => {
  it('lists users ten to a page and finds one by search', async () => {
    renderApp(<UsersPage groups={[{ id: "g1", name: "Analysts" }]} />)
    expect(await screen.findByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(11)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'user12@' } })
    expect(screen.getAllByRole('row')).toHaveLength(2)
    expect(screen.getByText('User 12')).toBeInTheDocument()
  })

  it('creates a user in a modal and confirms before disabling one', async () => {
    renderApp(<UsersPage groups={[{ id: "g1", name: "Analysts" }]} />)
    await screen.findByText('alice@example.com')
    fireEvent.click(screen.getByRole('button', { name: 'New user' }))
    const form = await screen.findByRole('dialog')
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Bob' } })
    fireEvent.change(within(form).getByLabelText(/email/i), { target: { value: 'b@x.test' } })
    const create = within(form).getByRole('button', { name: 'Create' })
    fireEvent.change(within(form).getByLabelText(/^password$/i),
      { target: { value: 'no capitals 1' } })
    expect(create).toBeDisabled()
    fireEvent.change(within(form).getByLabelText(/^password$/i),
      { target: { value: 'Abcdefgh1' } })
    fireEvent.change(within(form).getByLabelText(/repeat/i), { target: { value: 'Abcdefgh2' } })
    expect(within(form).getByRole('alert')).toHaveTextContent('The two passwords differ.')
    expect(create).toBeDisabled()
    fireEvent.change(within(form).getByLabelText(/repeat/i), { target: { value: 'Abcdefgh1' } })
    fireEvent.click(create)
    expect(await screen.findByText('User created')).toBeInTheDocument()
    expect(writes[0]).toEqual(['POST', 'admin/users', expect.objectContaining({
      email: 'b@x.test', display_name: 'Bob', password: 'Abcdefgh1' })])
    fireEvent.click(screen.getAllByRole('button', { name: /disable/i })[1] as HTMLElement)
    const ask = await screen.findByRole('alertdialog')
    fireEvent.click(within(ask).getByRole('button', { name: /disable/i }))
    expect(await screen.findByText('Account disabled')).toBeInTheDocument()
    expect(writes[1]).toEqual(['PATCH', 'admin/users/u2', { status: 'disabled' }])
  })
})
