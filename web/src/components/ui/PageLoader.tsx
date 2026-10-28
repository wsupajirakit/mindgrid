import { Activity } from 'lucide-react'
import { m } from '../../paraglide/messages.js'
import { Spinner } from './Spinner.tsx'

/** Shown while a page waits for what it needs (the router shows it after a short delay). */
export function PageLoader() {
  return (
    <div role="status" aria-live="polite"
      className="mg-fade grid min-h-[60vh] place-items-center p-6" data-state="open">
      <div className="flex flex-col items-center gap-4 text-muted-foreground">
        <span className="relative grid size-14 place-items-center">
          <span aria-hidden className="absolute inset-0 rounded-2xl bg-primary/20
            motion-safe:animate-ping" />
          <span className="relative grid size-14 place-items-center rounded-2xl bg-primary
            text-primary-foreground shadow-lg shadow-primary/30">
            <Activity className="size-6" />
          </span>
        </span>
        <span className="flex items-center gap-2 text-sm">
          <Spinner className="size-4" />{m.ui_loading()}
        </span>
      </div>
    </div>
  )
}
