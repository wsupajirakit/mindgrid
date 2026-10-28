import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'

export type BadgeTone = 'default' | 'secondary' | 'outline' | 'success' | 'warning'
  | 'destructive' | 'primary'

const TONES: Record<BadgeTone, string> = {
  default: 'bg-muted text-muted-foreground',
  secondary: 'bg-secondary text-secondary-foreground',
  outline: 'border border-border text-foreground',
  primary: 'bg-accent text-accent-foreground',
  success: 'bg-success/15 text-success',
  warning: 'bg-warning/15 text-warning',
  destructive: 'bg-destructive/15 text-destructive',
}

export function Badge({ tone = 'default', className, children }: { tone?: BadgeTone,
  className?: string, children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs',
      'font-medium whitespace-nowrap', TONES[tone], className)}>
      {children}
    </span>
  )
}
