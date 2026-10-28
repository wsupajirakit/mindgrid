import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { CategoriesPanel } from './components/CategoriesPanel.tsx'
import { pickOption } from '../../testing/select.ts'

describe('categories', () => {
  it('opens a restricted category to a group and to one person', async () => {
    renderApp(<CategoriesPanel projectId="p1" groups={[{ id: 'g1', name: 'Analysts' }]} />)
    const row = (await screen.findByText('macro')).closest('tr') as HTMLElement
    fireEvent.click(within(row).getByRole('button', { name: 'Access' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Restricted category/)).toBeInTheDocument()
    expect(await within(dialog).findByText('bob@example.com')).toBeInTheDocument()
    await pickOption(within(dialog).getByRole('combobox', { name: 'Add a group…' }), 'Analysts')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Access saved')).toBeInTheDocument()
    expect(writes[0]).toEqual(['PUT', 'categories/c1/group-grants/g1', { level: 1 }])
    await pickOption(within(dialog).getByRole('combobox', { name: 'Bob' }), 'Edit')
    await screen.findAllByText('Access saved')
    expect(writes[1]).toEqual(['PUT', 'categories/c1/grants/u2', { level: 3 }])
  })
})
