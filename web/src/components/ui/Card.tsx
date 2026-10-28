import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'

/** A surface. `title` / `description` / `actions` render the standard header. */
export function Card({ title, description, actions, footer, className, children }: {
  title?: ReactNode, description?: ReactNode, actions?: ReactNode, footer?: ReactNode,
  className?: string, children?: ReactNode }) {
  return (
    <section className={cn('flex flex-col rounded-xl border border-border bg-card',
      'text-card-foreground shadow-card', className)}>
      {title || actions ? (
        <CardHeader>
          <div className="min-w-0 flex-1">
            {title ? <CardTitle>{title}</CardTitle> : null}
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
        </CardHeader>
      ) : null}
      {children !== undefined ? <CardContent>{children}</CardContent> : null}
      {footer ? (
        <div className="flex items-center gap-2 border-t border-border px-5 py-3">{footer}</div>
      ) : null}
    </section>
  )
}

function CardHeader({ className, children }: { className?: string,
  children: ReactNode }) {
  return <div className={cn('flex items-start gap-3 px-5 pt-5', className)}>{children}</div>
}

function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold tracking-tight">{children}</h2>
}

function CardDescription({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-sm text-muted-foreground">{children}</p>
}

function CardContent({ className, children }: { className?: string,
  children: ReactNode }) {
  return <div className={cn('p-5', className)}>{children}</div>
}
