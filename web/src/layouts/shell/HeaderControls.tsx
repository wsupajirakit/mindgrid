// Header controls: language, theme (asks first) and the account menu (profile, password,
// menu layout, settings, sign out). Every choice is saved with the account.
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  KeyRound, LayoutTemplate, LogOut, Moon, PanelLeft, Settings, Sun, UserRound,
} from 'lucide-react'
import { useState, useSyncExternalStore } from 'react'
import { Avatar } from '../../components/ui/Avatar.tsx'
import { Button } from '../../components/ui/Button.tsx'
import { confirm } from '../../components/ui/Confirm.tsx'
import { Menu, MenuChoice, MenuItem, MenuSeparator } from '../../components/ui/Menu.tsx'
import { toast } from '../../components/ui/Toast.tsx'
import { PasswordDialog } from '../../features/auth/components/PasswordDialog.tsx'
import { ProfileDialog } from '../../features/auth/components/ProfileDialog.tsx'
import { type Me, signOut } from '../../features/auth/api.ts'
import { changeLocale, currentLocale } from '../../i18n/locale.ts'
import { m } from '../../paraglide/messages.js'
import {
  getNavLayout, type NavLayout, setNavLayout, subscribeNavLayout,
} from '../../stores/layout.ts'
import { getResolvedTheme, setThemeMode, subscribeTheme } from '../../stores/theme.ts'
import { useSavePreference } from './preferences.ts'

const failed = () => toast.error(m.ui_failed())

export function ThemeToggle() {
  const dark = useSyncExternalStore(subscribeTheme, () => getResolvedTheme() === 'dark')
  const save = useSavePreference()
  const toggle = async () => {
    const ok = await confirm({ title: dark ? m.theme_to_light() : m.theme_to_dark(),
      description: m.theme_saved_note(), confirmLabel: dark ? m.theme_light() : m.theme_dark() })
    if (!ok) return
    const mode = dark ? 'light' : 'dark'
    if (!await save('ui.theme', mode, () => setThemeMode(mode))) failed()
  }
  return (
    <Button variant="ghost" size="icon" aria-label={m.theme_toggle()}
      onClick={() => void toggle()}>
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
}

export function LocaleToggle() {
  const save = useSavePreference()
  const locale = currentLocale()
  const next = locale === 'th' ? 'en' : 'th'
  return (
    <Button variant="ghost" size="sm" aria-label={m.lang_toggle()}
      className="w-11 font-semibold tracking-wide"
      onClick={() => void save('ui.locale', next, () => changeLocale(next))
        .then((ok) => { if (!ok) failed() })}>
      {locale.toUpperCase()}
    </Button>
  )
}

function LayoutChoice() {
  const layout = useSyncExternalStore(subscribeNavLayout, getNavLayout)
  const save = useSavePreference()
  const pick = async (value: NavLayout) => {
    if (value === layout) return
    if (await save('ui.layout', value, () => setNavLayout(value))) toast.success(m.layout_saved())
    else failed()
  }
  return (
    <MenuChoice label={m.layout_title()} value={layout} onChange={(v) => void pick(v)}
      options={[
        { value: 'sidebar', label: m.layout_sidebar(), icon: <PanelLeft /> },
        { value: 'mega', label: m.layout_mega(), icon: <LayoutTemplate /> },
      ]} />
  )
}

function Identity({ me }: { me: Me }) {
  return (
    <div className="flex items-center gap-3">
      <Avatar name={me.display_name} avatar={me.avatar} size="lg" />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{me.display_name}</p>
        <p className="truncate text-xs text-muted-foreground">{me.email}</p>
        <p className="mt-1 text-xs text-primary">
          {me.system_role === 'superadmin' ? m.role_superadmin() : m.role_user()}
        </p>
      </div>
    </div>
  )
}

export function AccountMenu({ me }: { me: Me }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<'profile' | 'password' | null>(null)
  const leave = async () => {
    const ok = await confirm({ title: m.signout_title(), description: m.signout_text(),
      confirmLabel: m.action_sign_out(), tone: 'destructive' })
    if (!ok) return
    await signOut().catch(() => undefined)
    queryClient.clear()
    await navigate({ to: '/login' })
  }
  return (
    <>
      <Menu label={<Identity me={me} />} trigger={(
        <button type="button" aria-label={m.account_menu()}
          className="rounded-full transition hover:opacity-90">
          <Avatar name={me.display_name} avatar={me.avatar} />
        </button>
      )}>
        <MenuItem icon={<UserRound />} onSelect={() => setDialog('profile')}>
          {m.account_profile()}
        </MenuItem>
        <MenuItem icon={<KeyRound />} onSelect={() => setDialog('password')}>
          {m.account_password()}
        </MenuItem>
        <MenuItem icon={<Settings />} onSelect={() => void navigate({ to: '/settings' })}>
          {m.nav_settings()}
        </MenuItem>
        <MenuSeparator />
        <LayoutChoice />
        <MenuSeparator />
        <MenuItem icon={<LogOut />} tone="destructive" onSelect={() => void leave()}>
          {m.action_sign_out()}
        </MenuItem>
      </Menu>
      {dialog === 'profile' ? (
        <ProfileDialog me={me} open onOpenChange={(o) => { if (!o) setDialog(null) }} />
      ) : null}
      <PasswordDialog open={dialog === 'password'}
        onOpenChange={(o) => { if (!o) setDialog(null) }} />
    </>
  )
}
