import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Tabs } from './Tabs.tsx'
import { pickOption } from '../../testing/select.ts'

const LABEL = 'Sections'

function Sections() {
  const [tab, setTab] = useState('docs')
  return (
    <Tabs defaultValue="docs" value={tab} onValueChange={setTab} label={LABEL} groups={[
      { label: 'Knowledge', items: [{ value: 'docs', label: 'Documents', content: 'docs-body' }] },
      { label: 'Manage', items: [{ value: 'people', label: 'People', content: 'people-body' }] },
    ]} />
  )
}

describe('grouped section menu', () => {
  it('shows group headings, switches sections and offers a picker on small screens', async () => {
    render(<Sections />)
    expect(screen.getByText('Knowledge')).toBeInTheDocument()
    expect(screen.getByText('docs-body')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'People' }))
    expect(screen.getByText('people-body')).toBeInTheDocument()
    const picker = screen.getByRole('combobox', { name: 'Sections' })
    await pickOption(picker, 'Documents')
    expect(screen.getByText('docs-body')).toBeInTheDocument()
    expect(screen.getByRole('tablist', { name: 'Sections' }))
      .toHaveAttribute('aria-orientation', 'vertical')
  })
})
