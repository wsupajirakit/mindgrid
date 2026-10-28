// Themed confirmation (Radix AlertDialog), never window.confirm: `await confirm({...})`
// resolves true on the confirm button, false on cancel / Escape. <ConfirmHost /> renders it.
import { AlertDialog as Radix } from 'radix-ui'
import { type ReactNode, useSyncExternalStore } from 'react'
import { m } from '../../paraglide/messages.js'
import { buttonClass } from './Button.tsx'

type Ask = { title: ReactNode, description?: ReactNode, confirmLabel?: string,
  tone?: 'default' | 'destructive' }
type Pending = Ask & { resolve: (ok: boolean) => void }

let pending: Pending | null = null
const listeners = new Set<() => void>()
const emit = () => { listeners.forEach((fn) => fn()) }

export function confirm(ask: Ask): Promise<boolean> {
  pending?.resolve(false)
  return new Promise((resolve) => { pending = { ...ask, resolve }; emit() })
}

function settle(ok: boolean) {
  pending?.resolve(ok)
  pending = null
  emit()
}

export function ConfirmHost() {
  const ask = useSyncExternalStore(
    (fn) => { listeners.add(fn); return () => listeners.delete(fn) },
    () => pending,
  )
  return (
    <Radix.Root open={ask !== null} onOpenChange={(open) => { if (!open) settle(false) }}>
      <Radix.Portal>
        <Radix.Overlay className="mg-fade fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]" />
        <Radix.Content className="mg-zoom fixed top-1/2 left-1/2 z-50 w-[calc(100vw-2rem)]
          max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border
          bg-popover p-6 text-popover-foreground shadow-2xl">
          <Radix.Title className="text-lg font-semibold">{ask?.title}</Radix.Title>
          <Radix.Description className="mt-2 text-sm text-muted-foreground">
            {ask?.description ?? ''}
          </Radix.Description>
          <div className="mt-6 flex justify-end gap-2">
            <Radix.Cancel className={buttonClass('outline')}>{m.ui_cancel()}</Radix.Cancel>
            <Radix.Action onClick={() => settle(true)}
              className={buttonClass(ask?.tone === 'destructive' ? 'destructive' : 'default')}>
              {ask?.confirmLabel ?? m.ui_confirm()}
            </Radix.Action>
          </div>
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  )
}
