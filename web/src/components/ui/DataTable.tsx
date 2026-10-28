// Table on TanStack Table v9: one feature set for every table in the app (search across
// columns, sorting, pagination), so features only describe columns. Search and paging run
// in the browser over the rows the page already holds.
import {
  columnFilteringFeature, type ColumnDef, createFilteredRowModel, createPaginatedRowModel,
  createSortedRowModel, filterFn_includesString, filterFns, flexRender, globalFilteringFeature,
  rowPaginationFeature, rowSortingFeature, type RowData, sortFn_alphanumeric, sortFns,
  tableFeatures, useTable,
} from '@tanstack/react-table'
import {
  ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
} from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'
import { Button } from './Button.tsx'
import { EmptyState } from './EmptyState.tsx'
import { Select } from './Select.tsx'
import { SearchBox } from './SearchBox.tsx'
import { Skeleton } from './Skeleton.tsx'

const features = tableFeatures({
  rowSortingFeature,
  columnFilteringFeature,
  globalFilteringFeature,
  rowPaginationFeature,
  sortedRowModel: createSortedRowModel(),
  filteredRowModel: createFilteredRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
  sortFns: { ...sortFns, alphanumeric: sortFn_alphanumeric },
  filterFns: { ...filterFns, includesString: filterFn_includesString },
})

/** A column of a DataTable (the only table type features use). */
export type Column<T extends RowData> = ColumnDef<typeof features, T>

const ARIA = { asc: 'ascending', desc: 'descending' } as const
const PAGE_SIZES = [10, 20, 50, 100]

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc') return <ArrowUp className="size-3.5" />
  if (sorted === 'desc') return <ArrowDown className="size-3.5" />
  return <ArrowUpDown className="size-3.5 opacity-40" />
}

type Table<T extends RowData> = ReturnType<typeof useTable<typeof features, T>>

function Head<T extends RowData>({ table }: { table: Table<T> }) {
  return (
    <thead className="bg-muted/50">
      {table.getHeaderGroups().map((group) => (
        <tr key={group.id} className="border-b border-border">
          {group.headers.map((header) => {
            const sorted = header.column.getIsSorted()
            const title = flexRender(header.column.columnDef.header, header.getContext())
            return (
              <th key={header.id} aria-sort={sorted ? ARIA[sorted] : 'none'}
                className="h-10 px-3 text-left align-middle text-xs font-medium tracking-wide
                  whitespace-nowrap text-muted-foreground uppercase">
                {header.column.getCanSort() ? (
                  <button type="button" onClick={header.column.getToggleSortingHandler()}
                    className="-ml-1 inline-flex items-center gap-1 rounded px-1
                      hover:text-foreground">
                    {title}<SortIcon sorted={sorted} />
                  </button>
                ) : title}
              </th>
            )
          })}
        </tr>
      ))}
    </thead>
  )
}

function Pager<T extends RowData>({ table, total, pageIndex, pageSize }: { table: Table<T>,
  total: number, pageIndex: number, pageSize: number }) {
  const start = total === 0 ? 0 : pageIndex * pageSize + 1
  const end = Math.min(total, start + pageSize - 1)
  const nav = [
    { label: m.ui_first(), icon: <ChevronsLeft />, go: () => table.firstPage(),
      can: table.getCanPreviousPage() },
    { label: m.ui_prev(), icon: <ChevronLeft />, go: () => table.previousPage(),
      can: table.getCanPreviousPage() },
    { label: m.ui_next(), icon: <ChevronRight />, go: () => table.nextPage(),
      can: table.getCanNextPage() },
    { label: m.ui_last(), icon: <ChevronsRight />, go: () => table.lastPage(),
      can: table.getCanNextPage() },
  ]
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm
      text-muted-foreground">
      <label className="flex items-center gap-2">
        <span>{m.ui_rows_per_page()}</span>
        <Select className="h-8 w-20" value={String(pageSize)}
          onChange={(v) => table.setPageSize(Number(v))}
          options={PAGE_SIZES.map((n) => ({ value: String(n), label: n }))} />
      </label>
      <div className="flex items-center gap-1">
        <span className="mr-2">
          {m.ui_range({ from: String(start), to: String(end), total: String(total) })}
        </span>
        {nav.map((b) => (
          <Button key={b.label} variant="outline" size="icon-sm" aria-label={b.label}
            disabled={!b.can} onClick={b.go}>{b.icon}</Button>
        ))}
      </div>
    </div>
  )
}

function LoadingRows({ columns }: { columns: number }) {
  return Array.from({ length: 3 }, (_, i) => (
    <tr key={i} className="border-b border-border last:border-0">
      {Array.from({ length: columns }, (_, j) => (
        <td key={j} className="px-3 py-3"><Skeleton className="h-4 w-full" /></td>
      ))}
    </tr>
  ))
}

export function DataTable<T extends RowData>({ data, columns, empty, toolbar, loading,
  onRowClick, searchable = true, pageSize = 10 }: { data: T[], columns: Column<T>[],
  empty: string, toolbar?: ReactNode, loading?: boolean, onRowClick?: (row: T) => void,
  searchable?: boolean, pageSize?: number }) {
  const [globalFilter, setGlobalFilter] = useState('')
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize })
  const table = useTable({
    features, data, columns, globalFilterFn: 'includesString',
    state: { globalFilter, pagination },
    onGlobalFilterChange: (v) => {
      setGlobalFilter(typeof v === 'function' ? v(globalFilter) : v)
      setPagination((p) => ({ ...p, pageIndex: 0 }))
    },
    onPaginationChange: (v) => setPagination(typeof v === 'function' ? v(pagination) : v),
  })
  const total = table.getFilteredRowModel().rows.length
  return (
    <div className="flex flex-col gap-3">
      {searchable || toolbar ? (
        <div className="flex flex-wrap items-center gap-2">
          {searchable ? <SearchBox value={globalFilter} onChange={table.setGlobalFilter} /> : null}
          <div className="ml-auto flex flex-wrap gap-2">{toolbar}</div>
        </div>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <Head table={table} />
          <tbody>
            {loading && data.length === 0 ? <LoadingRows columns={columns.length} />
              : table.getRowModel().rows.map((row) => (
                <tr key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={cn('border-b border-border transition-colors last:border-0',
                    'hover:bg-muted/40', onRowClick && 'cursor-pointer')}>
                  {row.getAllCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2.5 align-middle">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
        {!loading && total === 0 ? (
          <EmptyState text={data.length === 0 ? empty : m.ui_no_results()} />
        ) : null}
      </div>
      {total > PAGE_SIZES[0]! ? <Pager table={table} total={total} {...pagination} /> : null}
    </div>
  )
}
