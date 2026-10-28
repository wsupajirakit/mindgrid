// Ranked horizontal bars: label above, value at the bar's end (direct labels), thin bars
// with rounded data ends; optional stacked segments separated by a 2px surface gap.
import { cn } from '../../utils/cn.ts'
import { Legend } from './ChartCard.tsx'

export type Segment = { key: string, label: string, color: string }
export type BarRow = { label: string, sub?: string, values: Record<string, number> }

export function BarList({ rows, segments, max = 12 }: { rows: BarRow[], segments: Segment[],
  max?: number }) {
  const shown = rows.slice(0, max)
  const total = (r: BarRow) => segments.reduce((s, seg) => s + (r.values[seg.key] ?? 0), 0)
  const top = Math.max(1, ...shown.map(total))
  return (
    <div>
      <Legend series={segments} />
      <ul className="flex flex-col gap-3">
        {shown.map((r) => {
          const sum = total(r)
          return (
            <li key={`${r.label}-${r.sub ?? ''}`} className="flex flex-col gap-1"
              title={segments.map((s) => `${s.label}: ${r.values[s.key] ?? 0}`).join(' · ')}>
              <div className="flex items-baseline gap-2 text-sm">
                <span className="truncate font-medium">{r.label}</span>
                {r.sub ? (
                  <span className="truncate text-xs text-muted-foreground">{r.sub}</span>
                ) : null}
                <span className="ml-auto font-semibold tabular-nums">{sum.toLocaleString()}</span>
              </div>
              <div className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-[4px]
                bg-muted/60">
                {segments.map((seg) => {
                  const v = r.values[seg.key] ?? 0
                  if (!v) return null
                  return (
                    <svg key={seg.key} viewBox="0 0 10 10" preserveAspectRatio="none"
                      className={cn('h-full first:rounded-l-[4px] last:rounded-r-[4px]')}
                      style={{ width: `${(v / top) * 100}%` }} aria-hidden>
                      <rect width="10" height="10" fill={seg.color} />
                    </svg>
                  )
                })}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
