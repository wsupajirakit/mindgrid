import { useEffect, useState } from 'react'

/** True once `active` has stayed true for `ms` (a short wait shows nothing). */
export function useDelayedFlag(active: boolean, ms: number) {
  const [elapsed, setElapsed] = useState(false)
  useEffect(() => {
    if (!active) return undefined
    const timer = setTimeout(() => setElapsed(true), ms)
    return () => { clearTimeout(timer); setElapsed(false) }
  }, [active, ms])
  return active && elapsed
}
