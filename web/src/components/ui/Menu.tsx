// Dropdown menu (Radix: keyboard navigation, typeahead, aria wiring).
import { DropdownMenu as Radix } from 'radix-ui'
import { Check } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'

export function Menu({ trigger, children, align = 'end', label }: { trigger: ReactNode,
  children: ReactNode, align?: 'start' | 'end', label?: ReactNode }) {
  return (
    <Radix.Root>
      <Radix.Trigger asChild>{trigger}</Radix.Trigger>
      <Radix.Portal>
        <Radix.Content align={align} sideOffset={8}
          className="mg-pop z-50 min-w-56 rounded-xl border border-border bg-popover p-1
            text-popover-foreground shadow-xl">
          {label ? <div className="px-2 py-2">{label}</div> : null}
          {label ? <Radix.Separator className="my-1 h-px bg-border" /> : null}
          {children}
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  )
}

export function MenuItem({ icon, onSelect, tone, children }: { icon?: ReactNode,
  onSelect: () => void, tone?: 'destructive', children: ReactNode }) {
  return (
    <Radix.Item onSelect={onSelect}
      className={cn('flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm',
        'outline-none data-[highlighted]:bg-muted [&_svg]:size-4',
        tone === 'destructive' && 'text-destructive')}>
      {icon}
      {children}
    </Radix.Item>
  )
}

export function MenuSeparator() {
  return <Radix.Separator className="my-1 h-px bg-border" />
}

/** A titled set of choices where exactly one is picked (shown with a check). */
export function MenuChoice<T extends string>({ label, value, options, onChange }: {
  label: string, value: T, options: { value: T, label: string, icon?: ReactNode }[],
  onChange: (value: T) => void }) {
  return (
    <>
      <Radix.Label className="px-2 pt-2 pb-1 text-xs font-medium text-muted-foreground">
        {label}
      </Radix.Label>
      <Radix.RadioGroup value={value} onValueChange={(v) => onChange(v as T)}>
        {options.map((o) => (
          <Radix.RadioItem key={o.value} value={o.value}
            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm
              outline-none data-[highlighted]:bg-muted [&_svg]:size-4">
            {o.icon}
            <span className="flex-1">{o.label}</span>
            <Radix.ItemIndicator><Check className="text-primary" /></Radix.ItemIndicator>
          </Radix.RadioItem>
        ))}
      </Radix.RadioGroup>
    </>
  )
}
