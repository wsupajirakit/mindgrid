// The app's destinations, shared by the side menu, the mega menu and the mobile drawer.
import {
  BookOpenCheck, BrainCircuit, ChartNoAxesCombined, FolderKanban, KeyRound, Radio, ScrollText,
  Settings, ShieldCheck, Users, UsersRound, Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { m } from '../../paraglide/messages.js'

export type NavItem = { to: string, label: () => string, description: () => string,
  icon: ReactNode }

export const WORKSPACE: NavItem[] = [
  { to: '/dashboard', label: () => m.nav_dashboard(), description: () => m.nav_desc_dashboard(),
    icon: <ChartNoAxesCombined /> },
  { to: '/projects', label: () => m.nav_projects(), description: () => m.nav_desc_projects(),
    icon: <FolderKanban /> },
  { to: '/results', label: () => m.nav_results(), description: () => m.nav_desc_results(),
    icon: <BookOpenCheck /> },
  { to: '/playbooks', label: () => m.nav_playbooks(), description: () => m.nav_desc_playbooks(),
    icon: <Workflow /> },
  { to: '/logs', label: () => m.nav_logs(), description: () => m.nav_desc_logs(),
    icon: <ScrollText /> },
  { to: '/settings', label: () => m.nav_settings(), description: () => m.nav_desc_settings(),
    icon: <Settings /> },
]

export const ADMIN: NavItem[] = [
  { to: '/admin/users', label: () => m.nav_users(), description: () => m.nav_desc_users(),
    icon: <Users /> },
  { to: '/admin/groups', label: () => m.nav_groups(), description: () => m.nav_desc_groups(),
    icon: <UsersRound /> },
  { to: '/admin/api-keys', label: () => m.nav_api_keys(),
    description: () => m.nav_desc_api_keys(), icon: <KeyRound /> },
  { to: '/admin/events', label: () => m.nav_events(), description: () => m.nav_desc_events(),
    icon: <Radio /> },
  { to: '/admin/synapse', label: () => m.nav_synapse(), description: () => m.nav_desc_synapse(),
    icon: <BrainCircuit /> },
  { to: '/admin/settings', label: () => m.nav_system(), description: () => m.nav_desc_system(),
    icon: <ShieldCheck /> },
]
