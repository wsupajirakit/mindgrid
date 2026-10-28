// Top bar with a mega menu: sections on the left (icon, title, one line each), the chosen
// section's destinations in a two-column grid on the right, and a call to action below.
// Once open, the panel stays until its close button is pressed (or a destination is
// chosen): moving the pointer away or clicking elsewhere does not close it.
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  ChevronDown, ChevronRight, FolderKanban, LayoutGrid, ShieldCheck, X,
} from 'lucide-react'
import { type ReactNode, type Ref, useEffect, useId, useRef, useState } from 'react'
import { buttonClass } from '../../components/ui/Button.tsx'
import type { Me } from '../../features/auth/api.ts'
import { projectsQuery } from '../../features/projects/api.ts'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'
import { ADMIN, WORKSPACE } from './nav.tsx'

type Section = 'workspace' | 'projects' | 'admin'
type Destination = { key: string, link: ReactNode }

const tile = (hue: string) => ({ color: `var(${hue})`,
  background: `color-mix(in oklab, var(${hue}) 16%, transparent)` })

function SectionButton({ active, onPick, icon, hue, title, text }: { active: boolean,
  onPick: () => void, icon: ReactNode, hue: string, title: string, text: string }) {
  return (
    <button type="button" onClick={onPick} aria-pressed={active}
      className={cn('glow-hover flex w-full items-start gap-3 rounded-xl p-3 text-left',
        active ? 'glow-select bg-card' : 'hover:bg-muted/60')}>
      <span style={tile(hue)} className="grid size-10 shrink-0 place-items-center
        rounded-full [&_svg]:size-5">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{text}</span>
      </span>
      {active ? <ChevronRight className="mt-3 size-4 text-muted-foreground" /> : null}
    </button>
  )
}

function itemLink(onPick: () => void, to: string, icon: ReactNode, label: string, sub?: string,
  params?: Record<string, string>) {
  return (
    <Link to={to} params={params} onClick={onPick}
        className="glow-hover flex items-center gap-3 rounded-lg px-2 py-2 text-sm
          hover:bg-muted [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-primary"
        activeProps={{ className: 'glow-select bg-accent text-accent-foreground' }}>
        {icon}
        <span className="min-w-0">
          <span className="block truncate font-medium">{label}</span>
          {sub ? <span className="block truncate text-xs text-muted-foreground">{sub}</span>
            : null}
        </span>
    </Link>
  )
}

function useDestinations(section: Section, onPick: () => void): Destination[] {
  const projects = useQuery(projectsQuery())
  if (section === 'projects') {
    return (projects.data ?? []).slice(0, 10).map((p) => ({ key: p.id,
      link: itemLink(onPick, '/projects/$projectId', <FolderKanban />, p.name, p.slug,
        { projectId: p.id }) }))
  }
  return (section === 'admin' ? ADMIN : WORKSPACE).map((n) => ({ key: n.to,
    link: itemLink(onPick, n.to, n.icon, n.label(), n.description()) }))
}

const CTA: Record<Section, { text: () => string, label: () => string, to: string,
  search?: Record<string, unknown> }> = {
  workspace: { text: () => m.mega_cta_workspace(), label: () => m.mega_open_results(),
    to: '/results' },
  projects: { text: () => m.mega_cta_projects(), label: () => m.mega_new_project(),
    to: '/projects', search: { new: true } },
  admin: { text: () => m.mega_cta_admin(), label: () => m.mega_manage_users(),
    to: '/admin/users' },
}

const HEADINGS: Record<Section, () => string> = {
  workspace: () => m.nav_group_workspace(), projects: () => m.mega_projects_of(),
  admin: () => m.nav_group_admin(),
}

function CloseButton({ onClose, ref }: { onClose: () => void,
  ref: Ref<HTMLButtonElement> }) {
  return (
    <button ref={ref} type="button" onClick={onClose} aria-label={m.mega_close()}
      className="grid size-11 shrink-0 place-items-center rounded-full bg-destructive/15
        text-destructive shadow-[0_0_22px_var(--glow-danger)] ring-1 ring-destructive/50
        transition hover:bg-destructive/25 hover:shadow-[0_0_30px_var(--glow-danger)]
        focus-visible:ring-2 focus-visible:ring-destructive focus-visible:outline-none">
      <X className="size-5" strokeWidth={2.5} />
    </button>
  )
}

function Panel({ me, id, onClose }: { me: Me | undefined, id: string, onClose: () => void }) {
  const [section, setSection] = useState<Section>('workspace')
  const destinations = useDestinations(section, onClose)
  const close = useRef<HTMLButtonElement>(null)
  useEffect(() => { close.current?.focus() }, [])
  const cta = CTA[section]
  return (
    <div id={id} role="region" aria-label={m.mega_explore()}
      className="grid gap-0 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <div className="flex flex-col gap-1 bg-muted/40 p-5">
        <p className="mb-2 px-3 text-[11px] font-semibold tracking-wider text-muted-foreground
          uppercase">{m.mega_sections()}</p>
        <SectionButton active={section === 'workspace'} onPick={() => setSection('workspace')}
          icon={<LayoutGrid />} hue="--hue-1" title={m.nav_group_workspace()}
          text={m.mega_workspace_desc()} />
        <SectionButton active={section === 'projects'} onPick={() => setSection('projects')}
          icon={<FolderKanban />} hue="--hue-2" title={m.nav_projects()}
          text={m.mega_projects_desc()} />
        {me?.system_role === 'superadmin' ? (
          <SectionButton active={section === 'admin'} onPick={() => setSection('admin')}
            icon={<ShieldCheck />} hue="--hue-3" title={m.nav_group_admin()}
            text={m.mega_admin_desc()} />
        ) : null}
      </div>
      <div className="flex flex-col p-5">
        <div className="mb-3 flex items-center justify-between gap-4 pl-2">
          <p className="text-[11px] font-semibold tracking-wider text-muted-foreground
            uppercase">{HEADINGS[section]()}</p>
          <CloseButton onClose={onClose} ref={close} />
        </div>
        {destinations.length === 0 ? (
          <p className="px-2 text-sm text-muted-foreground">{m.mega_no_projects()}</p>
        ) : (
          <ul className="grid gap-1 sm:grid-cols-2">
            {destinations.map((d) => <li key={d.key}>{d.link}</li>)}
          </ul>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-3 border-t border-border pt-4
          sm:mt-5">
          <p className="min-w-0 flex-1 text-sm text-muted-foreground">{cta.text()}</p>
          <Link to={cta.to} search={cta.search} onClick={onClose}
            className={buttonClass('outline', 'sm')}>
            {cta.label()}
          </Link>
        </div>
      </div>
    </div>
  )
}

const topLink = 'inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium '
  + 'text-muted-foreground transition-colors hover:bg-muted hover:text-foreground '
  + '[&_svg]:size-4 [&_svg]:shrink-0'

/** The bar's navigation: the mega menu trigger, then the most used pages. */
export function MegaMenu({ me }: { me: Me | undefined }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  return (
    <nav className="relative hidden lg:block" aria-label={m.nav_label()}>
      <ul className="flex items-center gap-1">
        <li>
          <button type="button" aria-expanded={open} aria-controls={panelId}
            onClick={() => setOpen(true)}
            className={cn(topLink, open && 'bg-muted text-foreground')}>
            <LayoutGrid aria-hidden />
            {m.mega_explore()}
            <ChevronDown aria-hidden className={cn('transition-transform', open && 'rotate-180')} />
          </button>
        </li>
        {WORKSPACE.slice(0, 4).map((n) => (
          <li key={n.to}>
            <Link to={n.to} className={topLink}
              activeProps={{ className: 'bg-accent text-accent-foreground' }}>
              {n.icon}
              {n.label()}
            </Link>
          </li>
        ))}
      </ul>
      {open ? (
        <div className="mg-pop absolute top-full left-0 z-40 mt-3 w-[min(56rem,calc(100vw-2rem))]
          overflow-hidden rounded-2xl border border-border bg-popover text-popover-foreground
          shadow-2xl">
          <Panel me={me} id={panelId} onClose={() => setOpen(false)} />
        </div>
      ) : null}
    </nav>
  )
}
