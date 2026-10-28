// The frame of every signed-in page. Two layouts, chosen per account in the account menu:
// a sidebar (collapses to icons) or a top bar with a mega menu. Small screens always get
// the drawer. Pages use the full width. Hosts for toasts and confirmations live here.
import { useQuery } from '@tanstack/react-query'
import { Menu as MenuIcon, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { type ReactNode, useState, useSyncExternalStore } from 'react'
import { Button } from '../components/ui/Button.tsx'
import { ConfirmHost } from '../components/ui/Confirm.tsx'
import { Toaster } from '../components/ui/Toast.tsx'
import { TooltipProvider } from '../components/ui/Tooltip.tsx'
import { meQuery } from '../features/auth/api.ts'
import { m } from '../paraglide/messages.js'
import { getNavLayout, subscribeNavLayout } from '../stores/layout.ts'
import { cn } from '../utils/cn.ts'
import { AccountMenu, LocaleToggle, ThemeToggle } from './shell/HeaderControls.tsx'
import { MegaMenu } from './shell/MegaMenu.tsx'
import { useAccountPreferences } from './shell/preferences.ts'
import { BrandMark, Sidebar } from './shell/Sidebar.tsx'

const COLLAPSED_KEY = 'mindgrid.sidebar'

function Drawer({ open, onOpenChange, children }: { open: boolean,
  onOpenChange: (open: boolean) => void, children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="mg-fade fixed inset-0 z-40 bg-overlay lg:hidden" />
        <Dialog.Content className="mg-slide fixed inset-y-0 left-0 z-50 w-72 border-r
          border-sidebar-border bg-sidebar shadow-2xl lg:hidden">
          <Dialog.Title className="sr-only">{m.ui_menu()}</Dialog.Title>
          <Dialog.Description className="sr-only">{m.nav_label()}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const me = useQuery(meQuery)
  const layout = useSyncExternalStore(subscribeNavLayout, getNavLayout)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSED_KEY) === '1')
  const [drawer, setDrawer] = useState(false)
  useAccountPreferences()
  const mega = layout === 'mega'
  const toggleCollapsed = () => {
    localStorage.setItem(COLLAPSED_KEY, collapsed ? '0' : '1')
    setCollapsed(!collapsed)
  }
  return (
    <TooltipProvider>
      <div className="flex min-h-screen">
        {mega ? null : (
          <aside className={cn('sticky top-0 hidden h-screen shrink-0 border-r',
            'border-sidebar-border bg-sidebar transition-[width] duration-200 lg:block',
            collapsed ? 'w-16' : 'w-64')}>
            <Sidebar me={me.data} collapsed={collapsed} />
          </aside>
        )}
        <Drawer open={drawer} onOpenChange={setDrawer}>
          <Sidebar me={me.data} collapsed={false} onPick={() => setDrawer(false)} />
        </Drawer>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b
            border-border bg-background/80 px-3 backdrop-blur sm:px-5">
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label={m.ui_menu()}
              onClick={() => setDrawer(true)}><MenuIcon /></Button>
            {mega ? (
              <div className="flex min-w-0 items-center gap-4">
                <span className="hidden lg:block"><BrandMark /></span>
                <MegaMenu me={me.data} />
              </div>
            ) : (
              <Button variant="ghost" size="icon" className="hidden lg:inline-flex"
                aria-label={collapsed ? m.ui_expand() : m.ui_collapse()}
                onClick={toggleCollapsed}>
                {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
              </Button>
            )}
            <div className="flex-1" />
            <LocaleToggle />
            <ThemeToggle />
            {me.data ? <AccountMenu me={me.data} /> : null}
          </header>
          <main className="w-full min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
      <Toaster />
      <ConfirmHost />
    </TooltipProvider>
  )
}
