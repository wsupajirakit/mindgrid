import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { changeLocale } from '../../i18n/locale.ts'
import { getCardsPerRow, setCardsPerRow } from '../../stores/cardsPerRow.ts'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { PlaybooksPage } from './components/PlaybooksPage.tsx'
import { PlaybooksPanel } from './components/PlaybooksPanel.tsx'

afterEach(() => { changeLocale('en'); setCardsPerRow(2) })

describe('project playbooks', () => {
  it('shows the assigned playbooks as cards and runs one in a modal', async () => {
    renderApp(<PlaybooksPanel projectId="p1" />)
    expect(await screen.findByText('v1 · Active')).toBeInTheDocument()
    expect(screen.getByText('What is a playbook?')).toBeInTheDocument()
    expect(screen.getByText('3 steps')).toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Run' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Filter, rank and keep the top rows.')).toBeInTheDocument()
    expect(await within(dialog).findByLabelText(/top_n/)).toHaveAttribute('placeholder', '10')
  })

  it('packs more cards per row in a compact layout and keeps the choice', async () => {
    renderApp(<PlaybooksPanel projectId="p1" />)
    await screen.findByText('3 steps')
    const group = screen.getByRole('radiogroup', { name: 'Cards per row' })
    expect(within(group).getByRole('radio', { name: '2 cards per row' })).toBeChecked()
    fireEvent.click(within(group).getByRole('radio', { name: '8 cards per row' }))
    expect(getCardsPerRow()).toBe(8)
    expect(localStorage.getItem('mindgrid.cards-per-row')).toBe('8')
    expect(await screen.findByText(/inputs · .* parameters · 3 steps/)).toBeInTheDocument()
    expect(screen.queryByText('v1 · Active')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run' })).not.toHaveTextContent('Run')
  })

  it('points to the Playbooks page when nothing is assigned', async () => {
    renderApp(<PlaybooksPanel projectId="p-none" />)
    expect(await screen.findByText(/No playbook is on for this project/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Playbooks' })).toHaveAttribute('href',
      '/playbooks')
  })

  it('shows the Thai title and summary when the interface is in Thai', async () => {
    renderApp(<PlaybooksPanel projectId="p1" />)
    await screen.findByText('Screen a table')
    changeLocale('th')
    expect(await screen.findByText('คัดกรองตาราง')).toBeInTheDocument()
    expect(screen.getByText('เก็บ จัดอันดับ คืนแถวต้น ๆ')).toBeInTheDocument()
    expect(screen.getByText('th')).toBeInTheDocument()
  })
})

describe('playbooks page', () => {
  it('asks before switching a playbook off for every project, then says so', async () => {
    renderApp(<PlaybooksPage superadmin />)
    fireEvent.click(await screen.findByRole('switch', { name: 'Switch off' }))
    const ask = await screen.findByRole('alertdialog')
    expect(ask).toHaveTextContent('Switch “Screen a table” off?')
    fireEvent.click(within(ask).getByRole('button', { name: 'Cancel' }))
    expect(writes).toHaveLength(0)
    fireEvent.click(screen.getByRole('switch', { name: 'Switch off' }))
    fireEvent.click(within(await screen.findByRole('alertdialog'))
      .getByRole('button', { name: 'Switch off' }))
    expect(await screen.findByText('Switched off')).toBeInTheDocument()
    expect(writes[0]?.[2]).toMatchObject({ enabled: false })
  })

  it('assigns a playbook to the ticked projects only', async () => {
    renderApp(<PlaybooksPage superadmin />)
    fireEvent.click(await screen.findByRole('button', { name: 'Assign to projects' }))
    const form = await screen.findByRole('dialog')
    fireEvent.click(within(form).getByRole('checkbox', { name: 'Every project' }))
    fireEvent.click(within(form).getByRole('checkbox', { name: 'Beta' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Projects saved')).toBeInTheDocument()
    expect(writes[0]).toEqual(['PUT', 'playbooks/core.table-screen/assignments',
      { all_projects: false, projects: { p1: true, p2: false } }])
  })

  it('saves a translation, and hides superadmin tools from others', async () => {
    const { unmount } = renderApp(<PlaybooksPage superadmin />)
    fireEvent.click(await screen.findByRole('button', { name: 'Translate' }))
    const form = await screen.findByRole('dialog')
    expect(within(form).getByLabelText('Title')).toHaveValue('คัดกรองตาราง')
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 'ตาราง' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Translation saved')).toBeInTheDocument()
    expect(writes[0]).toEqual(['PUT', 'admin/playbooks/core.table-screen/translations/th',
      { title: 'ตาราง', summary: 'เก็บ จัดอันดับ คืนแถวต้น ๆ' }])
    unmount()
    renderApp(<PlaybooksPage superadmin={false} />)
    expect(await screen.findByRole('button', { name: 'Assign to projects' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Translate' })).not.toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })
})

describe('project playbooks for a manager', () => {
  it('adds a playbook from the catalog and removes one after a confirm', async () => {
    renderApp(<PlaybooksPanel projectId="p-none" canManage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add playbook' }))
    const form = await screen.findByRole('dialog')
    fireEvent.click(within(form).getByRole('checkbox', { name: /Screen a table/ }))
    fireEvent.click(within(form).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Playbooks added')).toBeInTheDocument()
    expect(writes[0]?.slice(0, 2)).toEqual(['PUT', 'projects/p-none/playbooks/core.table-screen'])
    expect(writes[0]?.[2]).toMatchObject({ enabled: true })
  })

  it('removes a playbook from the project', async () => {
    renderApp(<PlaybooksPanel projectId="p1" canManage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    fireEvent.click(within(await screen.findByRole('alertdialog'))
      .getByRole('button', { name: 'Remove' }))
    expect(await screen.findByText('Playbook removed')).toBeInTheDocument()
    expect(writes[0]?.[2]).toMatchObject({ enabled: false })
  })
})
