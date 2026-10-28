import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

export function EmptyState({ text, icon, action }: { text: string, icon?: ReactNode,
  action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <div className="grid size-10 place-items-center rounded-full bg-muted text-muted-foreground">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <p className="max-w-sm text-sm text-muted-foreground">{text}</p>
      {action}
    </div>
  )
}
