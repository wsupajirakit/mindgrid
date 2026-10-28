import { cn } from '../../utils/cn.ts'

/** A slim indeterminate bar along the top edge of its container (or of the page with
 * `fixed`); renders nothing when inactive. */
export function TopProgress({ active, fixed, label, className }: { active: boolean,
  fixed?: boolean, label?: string, className?: string }) {
  if (!active) return null
  return (
    <div role="progressbar" aria-label={label} aria-busy
      className={cn('pointer-events-none inset-x-0 top-0 z-[60] h-[3px] overflow-hidden',
        'bg-primary/15', fixed ? 'fixed' : 'absolute', className)}>
      <div className="mg-progress h-full w-2/5 rounded-full bg-gradient-to-r from-primary/40
        via-primary to-primary/40 shadow-[0_0_12px_var(--primary)]" />
    </div>
  )
}
