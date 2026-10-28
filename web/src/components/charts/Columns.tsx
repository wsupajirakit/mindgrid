// Stacked columns over days. One y axis with a few recessive gridlines, rounded data ends
// on the top segment, a 2px surface gap between stacked segments, and a hover layer: the
// column under the pointer is highlighted and a tooltip lists its values.
import { useState } from 'react'
import { Legend } from './ChartCard.tsx'
import type { Segment } from './BarList.tsx'

export type DayRow = { day: string, values: Record<string, number> }

const W = 640
const H = 220
const PAD = { top: 12, right: 8, bottom: 26, left: 34 }

function niceMax(v: number): number {
  if (v <= 4) return 4
  const step = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / step) * step
}

export function Columns({ rows, segments, label }: { rows: DayRow[], segments: Segment[],
  label: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const totals = rows.map((r) => segments.reduce((s, g) => s + (r.values[g.key] ?? 0), 0))
  const top = niceMax(Math.max(1, ...totals))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const slot = plotW / Math.max(rows.length, 1)
  const bar = Math.max(3, Math.min(28, slot * 0.6))
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH
  const ticks = [0, top / 4, top / 2, (3 * top) / 4, top]
  const every = Math.max(1, Math.ceil(rows.length / 8))
  const picked = hover === null ? null : rows[hover]
  return (
    <div className="relative">
      <Legend series={segments} />
      <svg viewBox={`0 0 ${W} ${H}`} className="h-56 w-full" role="img" aria-label={label}
        onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)"
              strokeWidth="1" />
            <text x={PAD.left - 6} y={y(t) + 3} textAnchor="end" fontSize="10"
              fill="var(--muted-foreground)">{Math.round(t)}</text>
          </g>
        ))}
        {rows.map((r, i) => {
          const x = PAD.left + i * slot + (slot - bar) / 2
          let base = 0
          const parts = segments.filter((g) => (r.values[g.key] ?? 0) > 0)
          return (
            <g key={r.day} onMouseEnter={() => setHover(i)}>
              <rect x={PAD.left + i * slot} y={PAD.top} width={slot} height={plotH}
                fill={hover === i ? 'var(--muted)' : 'transparent'} opacity="0.6" />
              {parts.map((g, j) => {
                const v = r.values[g.key] ?? 0
                const y0 = y(base + v)
                const h = Math.max(1, y(base) - y0 - (j > 0 ? 2 : 0))
                base += v
                const topPart = j === parts.length - 1
                return (
                  <path key={g.key} fill={g.color}
                    d={topPart
                      ? `M${x},${y0 + h} v${-(h - 4)} q0,-4 4,-4 h${bar - 8} q4,0 4,4 v${h - 4} z`
                      : `M${x},${y0} h${bar} v${h} h${-bar} z`} />
                )
              })}
              {i % every === 0 ? (
                <text x={x + bar / 2} y={H - 8} textAnchor="middle" fontSize="10"
                  fill="var(--muted-foreground)">{r.day.slice(5)}</text>
              ) : null}
            </g>
          )
        })}
        <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--border)" />
      </svg>
      {picked ? (
        <div className="pointer-events-none absolute top-8 right-2 rounded-lg border
          border-border bg-popover px-3 py-2 text-xs shadow-lg">
          <p className="mb-1 font-semibold">{picked.day}</p>
          {segments.map((g) => (
            <p key={g.key} className="flex items-center gap-2 text-muted-foreground">
              <svg viewBox="0 0 10 10" className="size-2" aria-hidden>
                <rect width="10" height="10" rx="2" fill={g.color} />
              </svg>
              {g.label}
              <span className="ml-auto pl-3 font-medium text-foreground tabular-nums">
                {picked.values[g.key] ?? 0}
              </span>
            </p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
