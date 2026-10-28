import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'
import { Cover } from './Cover.tsx'

/** A card with a generated cover: icon and badges on the cover, then title, body, actions.
 * `compact` shrinks the cover, padding and title for dense grids. */
export function CoverCard({ seed, icon, badges, title, subtitle, children, actions,
  compact = false }: { seed: string, icon: ReactNode, badges?: ReactNode, title: string,
  subtitle?: string, children?: ReactNode, actions?: ReactNode, compact?: boolean }) {
  return (
    <article className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-border
      bg-card shadow-card transition hover:shadow-lg">
      <Cover seed={seed} className={compact ? 'h-16' : 'h-28'}>
        <div className={cn('flex h-full items-start justify-between gap-2',
          compact ? 'p-2' : 'p-3')}>
          <span className={cn('grid shrink-0 place-items-center rounded-xl bg-white/20',
            'text-white backdrop-blur', compact ? 'size-8 [&_svg]:size-4'
              : 'size-10 [&_svg]:size-5')}>{icon}</span>
          <div className="flex min-w-0 flex-wrap justify-end gap-1">{badges}</div>
        </div>
      </Cover>
      <div className={cn('flex flex-1 flex-col', compact ? 'gap-2 p-3' : 'gap-3 p-4')}>
        <div className="min-w-0">
          <h3 title={compact ? title : undefined} className={cn('font-semibold leading-tight',
            compact && 'line-clamp-2 text-sm')}>{title}</h3>
          {subtitle ? (
            <code className={cn('block truncate text-muted-foreground',
              compact ? 'text-[11px]' : 'text-xs')}>{subtitle}</code>
          ) : null}
        </div>
        {children}
        {actions ? (
          <div className={cn('mt-auto flex flex-wrap items-center border-t border-border',
            compact ? 'gap-1 pt-2' : 'gap-2 pt-3')}>
            {actions}
          </div>
        ) : null}
      </div>
    </article>
  )
}
