import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'


type Tone = 'info' | 'error' | 'ok' | 'warn'
const TONES: Record<Tone, string> = {
  info: 'border-border bg-muted/50 text-muted-foreground',
  error: 'border-destructive/40 bg-destructive/10 text-destructive',
  ok: 'border-success/40 bg-success/10 text-success',
  warn: 'border-warning/40 bg-warning/10 text-warning',
}
const ICONS = { info: Info, error: CircleAlert, ok: CircleCheck, warn: TriangleAlert }

/** An inline message with an icon, so its tone never rests on colour alone. */
export function Notice({ tone = 'info', className, children }: { tone?: Tone,
  className?: string, children: ReactNode }) {
  const Icon = ICONS[tone]
  return (
    <div role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2 rounded-lg border px-3 py-2 text-sm', TONES[tone],
        className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
