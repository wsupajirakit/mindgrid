import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { type Column, DataTable } from './DataTable.tsx'

type Row = { name: string, n: number }
const ROWS: Row[] = Array.from({ length: 25 }, (_, i) => ({ name: `item ${String(i + 1)}`,
  n: 25 - i }))
const COLUMNS: Column<Row>[] = [
  { accessorKey: 'name', header: () => 'Name' },
  { accessorKey: 'n', header: () => 'Count' },
]
const names = () => screen.getAllByRole('row').slice(1)
  .map((r) => within(r).getAllByRole('cell')[0]?.textContent)

describe('data table', () => {
  it('pages, searches and sorts the rows it holds', () => {
    render(<DataTable data={ROWS} columns={COLUMNS} empty="none" />)
    expect(names()).toHaveLength(10)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(names()[0]).toBe('item 11')
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'item 2' } })
    expect(names()).toEqual(['item 2', 'item 20', 'item 21', 'item 22', 'item 23', 'item 24',
      'item 25'])
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /count/i }))
    const sort = screen.getByRole('columnheader', { name: /count/i }).getAttribute('aria-sort')
    expect(names()[0]).toBe(sort === 'ascending' ? 'item 25' : 'item 1')
    expect(sort).toMatch(/ascending|descending/)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'nothing' } })
    expect(screen.getByText(/no results|nothing matches/i)).toBeInTheDocument()
  })
})
