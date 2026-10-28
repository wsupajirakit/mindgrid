// Themed single-choice picker (Radix: keyboard navigation, typeahead, aria wiring).
// Radix forbids an item with value "": an empty `value` shows the placeholder instead, and an
// "all"/"none" choice uses a sentinel such as `ALL`.
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import { Select as Radix } from 'radix-ui'
import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'
import { controlClass } from './Field.tsx'

/** Sentinel value for an "all" / "none" choice. */
export const ALL = '__all__'

export type SelectOption = { value: string, label: ReactNode, disabled?: boolean }
export type SelectGroup = { label: ReactNode, options: SelectOption[] }

function Item({ option }: { option: SelectOption }) {
  return (
    <Radix.Item value={option.value} disabled={option.disabled}
      className="relative flex cursor-pointer items-center gap-2 rounded-md py-2 pr-8 pl-2
        text-sm outline-none select-none data-[disabled]:pointer-events-none
        data-[disabled]:opacity-50 data-[highlighted]:bg-muted
        data-[state=checked]:font-medium data-[state=checked]:text-primary">
      <Radix.ItemText>{option.label}</Radix.ItemText>
      <Radix.ItemIndicator className="absolute right-2 inline-flex items-center">
        <Check className="size-4 text-primary" />
      </Radix.ItemIndicator>
    </Radix.Item>
  )
}

/** Controlled with `value` + `onChange`; leave `value` undefined for a one-shot picker. Pass
 * `options`, or `groups` for headed sections. */
export function Select({ value, onChange, options = [], groups, placeholder, className,
  disabled, 'aria-label': ariaLabel }: { value?: string, onChange: (value: string) => void,
  options?: SelectOption[], groups?: SelectGroup[], placeholder?: ReactNode,
  className?: string, disabled?: boolean, 'aria-label'?: string }) {
  return (
    <Radix.Root value={value} onValueChange={onChange} disabled={disabled}>
      <Radix.Trigger aria-label={ariaLabel}
        className={cn(controlClass, 'flex h-9 items-center justify-between gap-2 text-left',
          'hover:border-ring/60 data-[placeholder]:text-muted-foreground',
          'data-[state=open]:ring-2 data-[state=open]:ring-ring [&>span]:truncate', className)}>
        <Radix.Value placeholder={placeholder} />
        <Radix.Icon asChild>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        </Radix.Icon>
      </Radix.Trigger>
      <Radix.Portal>
        <Radix.Content position="popper" sideOffset={6}
          className="mg-pop z-50 max-h-[min(var(--radix-select-content-available-height),20rem)]
            min-w-(--radix-select-trigger-width) overflow-hidden rounded-xl border border-border
            bg-popover text-popover-foreground shadow-xl">
          <Radix.ScrollUpButton className="flex h-6 items-center justify-center">
            <ChevronUp className="size-4" />
          </Radix.ScrollUpButton>
          <Radix.Viewport className="p-1">
            {options.map((o) => <Item key={o.value} option={o} />)}
            {(groups ?? []).map((g, i) => (
              <Radix.Group key={i}>
                {i > 0 || options.length ? <Radix.Separator className="my-1 h-px bg-border" />
                  : null}
                <Radix.Label className="px-2 pt-2 pb-1 text-xs font-medium
                  text-muted-foreground">{g.label}</Radix.Label>
                {g.options.map((o) => <Item key={o.value} option={o} />)}
              </Radix.Group>
            ))}
          </Radix.Viewport>
          <Radix.ScrollDownButton className="flex h-6 items-center justify-center">
            <ChevronDown className="size-4" />
          </Radix.ScrollDownButton>
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  )
}
