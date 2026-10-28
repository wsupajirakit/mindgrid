// Accessible tabs (Radix: roving focus, arrow keys, aria wiring), in two layouts:
// - "top": a row of tabs over the content (a few peer views);
// - "side": a grouped section menu beside the content (many sections). Group headings,
//   icons and a highlighted active item; on small screens a grouped picker replaces it.
import { Tabs as Radix } from 'radix-ui'
import type { ReactNode } from 'react'
import { cn } from '../../utils/cn.ts'
import { Select } from './Select.tsx'

export type TabItem = { value: string, label: string, icon?: ReactNode, content: ReactNode }
export type TabGroup = { label: string, items: TabItem[] }

function TopTrigger({ item }: { item: TabItem }) {
  return (
    <Radix.Trigger value={item.value}
      className="-mb-px inline-flex shrink-0 items-center gap-1.5 border-b-2
        border-transparent px-3 py-2.5 text-sm font-medium text-muted-foreground
        transition-colors hover:text-foreground data-[state=active]:border-primary
        data-[state=active]:text-foreground [&_svg]:size-4">
      {item.icon}
      {item.label}
    </Radix.Trigger>
  )
}

function SideTrigger({ item }: { item: TabItem }) {
  return (
    <Radix.Trigger value={item.value}
      className={cn('glow-hover group flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5',
        'text-left data-[state=active]:glow-select',
        'text-sm text-muted-foreground transition-colors outline-none hover:bg-muted',
        'hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring',
        'data-[state=active]:bg-accent data-[state=active]:font-medium',
        'data-[state=active]:text-accent-foreground [&_svg]:size-4 [&_svg]:shrink-0')}>
      {item.icon}
      <span className="truncate">{item.label}</span>
    </Radix.Trigger>
  )
}

function SideMenu({ groups, value, onValueChange, label }: { groups: TabGroup[],
  value?: string, onValueChange?: (value: string) => void, label: string }) {
  return (
    <aside className="lg:sticky lg:top-20 lg:self-start">
      <div className="lg:hidden">
        <Select aria-label={label} value={value} onChange={(v) => onValueChange?.(v)}
          groups={groups.map((g) => ({ label: g.label,
            options: g.items.map((i) => ({ value: i.value, label: i.label })) }))} />
      </div>
      <Radix.List aria-label={label} className="hidden flex-col gap-5 rounded-xl border
        border-border bg-card p-3 shadow-card lg:flex">
        {groups.map((g) => (
          <div key={g.label} role="presentation" className="flex flex-col gap-0.5">
            <span className="px-2.5 pb-1 text-[11px] font-semibold tracking-wider
              text-muted-foreground/80 uppercase">{g.label}</span>
            {g.items.map((item) => <SideTrigger key={item.value} item={item} />)}
          </div>
        ))}
      </Radix.List>
    </aside>
  )
}

/** Uncontrolled with `defaultValue`, or controlled with `value` + `onValueChange` (deep
 * links). `items` makes a top row; `groups` (with `label` naming the menu) a side menu. */
export function Tabs({ items, groups, defaultValue, value, onValueChange, label = '' }: {
  defaultValue: string, value?: string, onValueChange?: (value: string) => void,
  items?: TabItem[], groups?: TabGroup[], label?: string }) {
  const all = groups ? groups.flatMap((g) => g.items) : (items ?? [])
  const contents = all.map((item) => (
    <Radix.Content key={item.value} value={item.value} className="min-w-0 outline-none">
      {item.content}
    </Radix.Content>
  ))
  if (groups) {
    return (
      <Radix.Root defaultValue={defaultValue} value={value} onValueChange={onValueChange}
        orientation="vertical" className="grid items-start gap-6
          lg:grid-cols-[15rem_minmax(0,1fr)]">
        <SideMenu groups={groups} value={value ?? defaultValue} onValueChange={onValueChange}
          label={label} />
        <div className="min-w-0">{contents}</div>
      </Radix.Root>
    )
  }
  return (
    <Radix.Root defaultValue={defaultValue} value={value} onValueChange={onValueChange}
      className="flex flex-col gap-5">
      <Radix.List className="flex flex-wrap border-b border-border">
        {all.map((item) => <TopTrigger key={item.value} item={item} />)}
      </Radix.List>
      {contents}
    </Radix.Root>
  )
}
