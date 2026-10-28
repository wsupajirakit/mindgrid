import type { ReactNode } from 'react'

/** Page title, one line on what the page is for, and its main actions. */
export function PageHeader({ title, description, actions, icon }: { title: string,
  description?: ReactNode, actions?: ReactNode, icon?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start gap-4">
      {icon ? (
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent
          text-accent-foreground [&_svg]:size-5">{icon}</div>
      ) : null}
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}
