import { LoaderCircle } from 'lucide-react'
import { cn } from '../../utils/cn.ts'

/** A turning circle; decorative (the busy control or region carries the state). */
export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle aria-hidden className={cn('motion-safe:animate-spin', className)} />
}
