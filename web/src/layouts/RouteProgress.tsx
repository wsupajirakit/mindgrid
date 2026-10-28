import { useRouterState } from '@tanstack/react-router'
import { TopProgress } from '../components/ui/TopProgress.tsx'
import { useDelayedFlag } from '../hooks/useDelayedFlag.ts'
import { m } from '../paraglide/messages.js'

const SHOW_AFTER_MS = 120 // a fast navigation shows no bar at all

/** The bar along the top of the window while the router loads the next page. */
export function RouteProgress() {
  const pending = useRouterState({ select: (s) => s.status === 'pending' })
  return <TopProgress active={useDelayedFlag(pending, SHOW_AFTER_MS)} fixed
    label={m.ui_loading()} />
}
