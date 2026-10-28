// Modal dialogs (Radix: focus trap, Escape, aria wiring). Every create/edit form opens in
// one; the footer holds the actions, the body scrolls when long.
import { X } from 'lucide-react'
import { Dialog as Radix } from 'radix-ui'
import type { FormEvent, ReactNode } from 'react'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'
import { Button } from './Button.tsx'

const WIDTHS = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }

export function Modal({ open, onOpenChange, title, description, size = 'md', footer,
  children }: { open: boolean, onOpenChange: (open: boolean) => void, title: ReactNode,
  description?: ReactNode, size?: keyof typeof WIDTHS, footer?: ReactNode,
  children: ReactNode }) {
  return (
    <Radix.Root open={open} onOpenChange={onOpenChange}>
      <Radix.Portal>
        <Radix.Overlay className="mg-fade fixed inset-0 z-50 bg-overlay backdrop-blur-[2px]" />
        <Radix.Content className={cn('mg-zoom fixed top-1/2 left-1/2 z-50 flex max-h-[90vh]',
          'w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border',
          'border-border bg-popover text-popover-foreground shadow-2xl', WIDTHS[size])}>
          <div className="flex items-start gap-3 border-b border-border px-6 py-4">
            <div className="min-w-0 flex-1">
              <Radix.Title className="text-lg font-semibold tracking-tight">{title}</Radix.Title>
              {description ? (
                <Radix.Description className="mt-1 text-sm text-muted-foreground">
                  {description}
                </Radix.Description>
              ) : <Radix.Description className="sr-only">{title}</Radix.Description>}
            </div>
            <Radix.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label={m.ui_close()}><X /></Button>
            </Radix.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer ? (
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
              {footer}
            </div>
          ) : null}
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  )
}

/** A modal whose body is a form: Enter submits, the primary button shows progress. */
export function FormModal({ open, onOpenChange, title, description, size, submitLabel, busy,
  disabled, onSubmit, children }: { open: boolean, onOpenChange: (open: boolean) => void,
  title: ReactNode, description?: ReactNode, size?: keyof typeof WIDTHS, submitLabel: string,
  busy?: boolean, disabled?: boolean, onSubmit: () => void | Promise<void>,
  children: ReactNode }) {
  const formId = `form-${String(title).replace(/\W+/g, '-').toLowerCase()}`
  const submit = (e: FormEvent) => { e.preventDefault(); void onSubmit() }
  return (
    <Modal open={open} onOpenChange={onOpenChange} title={title} description={description}
      size={size} footer={(
        <>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{m.ui_cancel()}</Button>
          <Button type="submit" form={formId} loading={busy} disabled={disabled}>
            {busy ? m.ui_working() : submitLabel}
          </Button>
        </>
      )}>
      <form id={formId} onSubmit={submit} className="flex flex-col gap-4">{children}</form>
    </Modal>
  )
}
