// Themed toasts (Radix Toast: announced to screen readers, swipe to dismiss). Anywhere in
// the app: toast.success(text) / toast.error(text); <Toaster /> renders them once.
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { Toast as Radix } from 'radix-ui'
import { useSyncExternalStore } from 'react'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'

type Tone = 'success' | 'error' | 'info'
type Item = { id: number, tone: Tone, title: string, text?: string }

let items: Item[] = []
let next = 1
const listeners = new Set<() => void>()
const emit = () => { listeners.forEach((fn) => fn()) }

function push(tone: Tone, title: string, text?: string) {
  items = [...items, { id: next++, tone, title, text }]
  emit()
}

function drop(id: number) {
  items = items.filter((t) => t.id !== id)
  emit()
}

export const toast = {
  success: (title: string, text?: string) => { push('success', title, text) },
  error: (title: string, text?: string) => { push('error', title, text) },
  info: (title: string, text?: string) => { push('info', title, text) },
}

const ICONS = { success: CircleCheck, error: CircleAlert, info: Info }
const TONES = { success: 'text-success', error: 'text-destructive', info: 'text-primary' }

export function Toaster() {
  const shown = useSyncExternalStore(
    (fn) => { listeners.add(fn); return () => listeners.delete(fn) },
    () => items,
  )
  return (
    <Radix.Provider swipeDirection="right" duration={4500}>
      {shown.map((t) => {
        const Icon = ICONS[t.tone]
        return (
          <Radix.Root key={t.id} onOpenChange={(open) => { if (!open) drop(t.id) }}
            className="mg-pop flex items-start gap-3 rounded-xl border border-border bg-popover
              p-4 text-popover-foreground shadow-xl">
            <Icon className={cn('mt-0.5 size-5 shrink-0', TONES[t.tone])} aria-hidden />
            <div className="min-w-0 flex-1">
              <Radix.Title className="text-sm font-semibold">{t.title}</Radix.Title>
              {t.text ? (
                <Radix.Description className="mt-0.5 text-sm break-words text-muted-foreground">
                  {t.text}
                </Radix.Description>
              ) : null}
            </div>
            <Radix.Close aria-label={m.ui_close()}
              className="rounded-md p-1 text-muted-foreground hover:bg-muted">
              <X className="size-4" />
            </Radix.Close>
          </Radix.Root>
        )
      })}
      <Radix.Viewport className="fixed right-0 bottom-0 z-[100] flex w-full max-w-sm flex-col
        gap-2 p-4 outline-none" />
    </Radix.Provider>
  )
}
