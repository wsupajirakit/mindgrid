// A chart in a card with a table view of the same numbers (identity never rests on colour
// alone, and every value stays readable for anyone who prefers or needs a table).
import { BarChart3, Table2 } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { m } from '../../paraglide/messages.js'
import { Card } from '../ui/Card.tsx'
import { EmptyState } from '../ui/EmptyState.tsx'
import { ViewToggle } from '../ui/ViewToggle.tsx'

export type TableView = { columns: string[], rows: (string | number)[][] }

export function ChartCard({ title, description, empty, table, className, children }: {
  title: string, description?: string, empty: boolean, table: TableView, className?: string,
  children: ReactNode }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  return (
    <Card title={title} description={description} className={className} actions={empty ? null : (
      <ViewToggle value={view} onChange={setView} options={[
        { value: 'chart', label: m.ui_view_chart(), icon: <BarChart3 /> },
        { value: 'table', label: m.ui_view_table(), icon: <Table2 /> },
      ]} />
    )}>
      {empty ? <EmptyState text={m.dash_no_data()} /> : view === 'chart' ? children : (
        <div className="max-h-80 overflow-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted text-left text-xs text-muted-foreground">
              <tr>
                {table.columns.map((c) => <th key={c} className="px-3 py-2 font-medium">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-border">
                  {r.map((v, j) => (
                    <td key={j}
                      className={j === 0 ? 'px-3 py-1.5' : 'px-3 py-1.5 text-right tabular-nums'}>
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

/** Legend: a colour swatch plus the series name in text ink (never the series colour). */
export function Legend({ series }: { series: { label: string, color: string }[] }) {
  if (series.length < 2) return null
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {series.map((s) => (
        <li key={s.label} className="inline-flex items-center gap-1.5">
          <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden>
            <rect width="10" height="10" rx="2" fill={s.color} />
          </svg>
          {s.label}
        </li>
      ))}
    </ul>
  )
}
