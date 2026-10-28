import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../utils/cn.ts'
import { Spinner } from './Spinner.tsx'

export type Variant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link'
export type Size = 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm'

const VARIANTS: Record<Variant, string> = {
  default: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90',
  secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  outline: 'border border-border bg-card shadow-sm hover:bg-muted',
  ghost: 'hover:bg-muted hover:text-foreground',
  destructive: 'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
  link: 'text-primary underline-offset-4 hover:underline',
}
const SIZES: Record<Size, string> = {
  default: 'h-9 px-4 py-2',
  sm: 'h-8 rounded-md px-3 text-xs',
  lg: 'h-10 rounded-md px-6',
  icon: 'size-9',
  'icon-sm': 'size-8',
}

export function buttonClass(variant: Variant = 'default', size: Size = 'default',
  className?: string) {
  return cn('inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md',
    'text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
    '[&_svg]:size-4 [&_svg]:shrink-0', VARIANTS[variant], SIZES[size], className)
}

/** `loading`: the action is on its way: a spinner and a sheen, not clickable, still at
 * full colour (a faded button reads as unavailable, not as working). */
export function Button({ variant = 'default', size = 'default', className, type = 'button',
  loading, disabled, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant, size?: Size, loading?: boolean }) {
  return (
    <button type={type} disabled={disabled || loading} aria-busy={loading || undefined}
      className={buttonClass(variant, size, cn(loading
        && 'mg-sheen relative overflow-hidden cursor-progress disabled:opacity-100', className))}
      {...props}>
      {loading ? <Spinner /> : null}
      {children}
    </button>
  )
}
