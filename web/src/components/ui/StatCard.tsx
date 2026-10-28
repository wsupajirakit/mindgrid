import type { ReactNode } from 'react'

/** One headline number with its label (a stat tile, not a chart). */
export function StatCard({ label, value, hint, icon }: { label: string, value: ReactNode,
  hint?: ReactNode, icon?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-4
      shadow-card">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      {icon ? (
        <div className="grid size-9 place-items-center rounded-lg bg-accent text-accent-foreground
          [&_svg]:size-4">{icon}</div>
      ) : null}
    </div>
  )
}
