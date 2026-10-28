// Segmented control (Radix radio group: arrow keys move and pick, one tab stop).
import { RadioGroup } from 'radix-ui'
import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'
import { Tooltip } from './Tooltip.tsx'

export type ViewOption<V extends string> = { value: V, label: ReactNode, icon?: ReactNode,
  hint?: string }

/** Chooses how a list is shown (cards, table, density, ...). `hint` names an option for
 * screen readers and shows as its tooltip; `size="md"` gives larger targets with the
 * picked option in the primary colour. */
export function ViewToggle<V extends string>({ value, onChange, options, label, size = 'sm' }: {
  value: V, onChange: (value: V) => void, options: ViewOption<V>[], label?: string,
  size?: 'sm' | 'md' }) {
  const md = size === 'md'
  return (
    <RadioGroup.Root value={value} onValueChange={(v) => onChange(v as V)} aria-label={label}
      orientation="horizontal" loop
      className={cn('inline-flex rounded-lg border border-border bg-muted/50',
        md ? 'gap-0.5 p-1' : 'p-0.5')}>
      {options.map((o) => {
        const item = (
          <RadioGroup.Item key={o.value} value={o.value} aria-label={o.hint}
            className={cn('inline-flex items-center justify-center gap-1.5 rounded-md',
              'font-medium text-muted-foreground transition-colors outline-none',
              'focus-visible:ring-2 focus-visible:ring-ring',
              'data-[state=unchecked]:hover:text-foreground',
              md ? 'h-8 min-w-12 px-2.5 text-sm tabular-nums [&_svg]:size-4'
                : 'h-7 px-2.5 text-xs [&_svg]:size-3.5',
              md ? 'data-[state=unchecked]:hover:bg-card data-[state=checked]:bg-primary'
                + ' data-[state=checked]:text-primary-foreground data-[state=checked]:shadow-sm'
                : 'data-[state=checked]:bg-card data-[state=checked]:text-foreground'
                + ' data-[state=checked]:shadow-sm')}>
            {o.icon}{o.label}
          </RadioGroup.Item>
        )
        return o.hint
          ? <Tooltip key={o.value} text={o.hint} side="bottom">{item}</Tooltip>
          : item
      })}
    </RadioGroup.Root>
  )
}
