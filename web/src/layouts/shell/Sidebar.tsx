import { Link } from '@tanstack/react-router'
import { Activity } from 'lucide-react'
import { Tooltip } from '../../components/ui/Tooltip.tsx'
import type { Me } from '../../features/auth/api.ts'
import { useBrand } from '../../hooks/useBrand.ts'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'
import { ADMIN, type NavItem, WORKSPACE } from './nav.tsx'

function NavLinks({ items, collapsed, onPick }: { items: NavItem[], collapsed: boolean,
  onPick?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {items.map((item) => {
        const link = (
          <Link to={item.to} onClick={onPick}
            className={cn('flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium',
              'text-sidebar-foreground transition-colors hover:bg-sidebar-accent [&_svg]:size-4',
              '[&_svg]:shrink-0', collapsed && 'justify-center px-0')}
            activeProps={{ className: 'bg-accent text-accent-foreground hover:bg-accent' }}>
            {item.icon}
            {collapsed ? <span className="sr-only">{item.label()}</span> : item.label()}
          </Link>
        )
        return (
          <li key={item.to}>
            {collapsed ? <Tooltip text={item.label()}>{link}</Tooltip> : link}
          </li>
        )
      })}
    </ul>
  )
}

/** The brand mark linking home (sidebar top, mega menu bar). */
export function BrandMark({ collapsed = false, onPick }: { collapsed?: boolean,
  onPick?: () => void }) {
  const brand = useBrand()
  return (
    <Link to="/dashboard" onClick={onPick}
      className={cn('flex h-10 shrink-0 items-center gap-2.5 px-1.5',
        collapsed && 'justify-center')}>
      <span className="grid size-8 place-items-center rounded-lg bg-primary
        text-primary-foreground shadow-sm"><Activity className="size-4" /></span>
      {collapsed ? null : <span className="truncate text-base font-semibold">{brand?.name}</span>}
    </Link>
  )
}

export function Sidebar({ me, collapsed, onPick }: { me: Me | undefined, collapsed: boolean,
  onPick?: () => void }) {
  const group = (text: string) => collapsed ? <div className="my-2 h-px bg-sidebar-border" />
    : <p className="px-2.5 pt-4 pb-1 text-[11px] font-semibold tracking-wider
      text-muted-foreground uppercase">{text}</p>
  return (
    <nav aria-label={m.nav_label()} className="flex h-full flex-col gap-1 overflow-y-auto p-3">
      <div className="mb-2"><BrandMark collapsed={collapsed} onPick={onPick} /></div>
      {group(m.nav_group_workspace())}
      <NavLinks items={WORKSPACE} collapsed={collapsed} onPick={onPick} />
      {me?.system_role === 'superadmin' ? (
        <>
          {group(m.nav_group_admin())}
          <NavLinks items={ADMIN} collapsed={collapsed} onPick={onPick} />
        </>
      ) : null}
    </nav>
  )
}
