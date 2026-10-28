import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { CopyProjectButton } from './components/CopyProjectDialog.tsx'

describe('copy to another project', () => {
  it('copies the ticked categories and the playbook choices', async () => {
    renderApp(<CopyProjectButton projectId="p1" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Copy to project' }))
    const form = await screen.findByRole('dialog')
    const into = within(form).getByLabelText('Copy into')
    fireEvent.click(into)
    await screen.findByRole('option', { name: 'Beta' })
    expect(screen.queryByRole('option', { name: 'Alpha' })).toBeNull()
    fireEvent.click(screen.getByRole('option', { name: 'Beta' }))
    fireEvent.click(await within(form).findByRole('checkbox', { name: 'Macro' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Copy' }))
    expect(await screen.findByText('Copied 1 categories, 3 documents, 1 playbook choices'))
      .toBeInTheDocument()
    expect(writes[0]).toEqual(['POST', 'admin/projects/p1/copy',
      { target_project_id: 'p2', category_ids: ['c1'], playbooks: true }])
  })
})
