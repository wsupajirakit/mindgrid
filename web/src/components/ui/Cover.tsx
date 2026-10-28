// Card covers drawn from a seed (e.g. a playbook id): the same seed always gives the same
// picture, different seeds differ. Pure SVG: no image files, nothing fetched.
import { useId } from 'react'
import { cn } from '../../utils/cn.ts'

const PAIRS: [string, string][] = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [
  `var(--cover-${String(i)}-a)`, `var(--cover-${String(i)}-b)`])

function seedOf(text: string): number {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0
  return h
}

function Pattern({ kind, seed }: { kind: number, seed: number }) {
  const ink = 'var(--ink-20)'
  const strong = 'var(--ink-45)'
  if (kind === 0) {  // rising bars, like a chart
    return <g>{Array.from({ length: 9 }, (_, i) => {
      const h = 18 + ((seed >> (i * 3)) % 46)
      return <rect key={i} x={20 + i * 30} y={110 - h} width="16" height={h} rx="4"
        fill={i === 6 ? strong : ink} />
    })}</g>
  }
  if (kind === 1) {  // flowing lines
    return <g fill="none" strokeWidth="3" strokeLinecap="round">
      {[0, 1, 2, 3].map((i) => (
        <path key={i} stroke={i === 1 ? strong : ink}
          d={`M-10 ${70 + i * 14} C 60 ${30 + i * 18}, 140 ${110 - i * 10}, 300 ${40 + i * 16}`} />
      ))}</g>
  }
  if (kind === 2) {  // concentric rings
    return <g fill="none" stroke={ink} strokeWidth="2.5">
      {[18, 36, 54, 72, 90].map((r) => <circle key={r} cx="230" cy="30" r={r} />)}
      <circle cx="230" cy="30" r="8" fill={strong} stroke="none" /></g>
  }
  return <g>{Array.from({ length: 40 }, (_, i) => (  // dot field
    <circle key={i} cx={14 + (i % 10) * 28} cy={18 + Math.floor(i / 10) * 26}
      r={(seed >> i) % 3 === 0 ? 5 : 2.5} fill={(seed >> i) % 5 === 0 ? strong : ink} />
  ))}</g>
}

export function Cover({ seed, className, children }: { seed: string, className?: string,
  children?: React.ReactNode }) {
  const n = seedOf(seed)
  const [from, to] = PAIRS[n % PAIRS.length]!
  const gradient = `cv-${useId().replace(/:/g, '')}`
  return (
    <div className={cn('relative overflow-hidden', className)}>
      <svg viewBox="0 0 280 120" preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 size-full" aria-hidden>
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={from} /><stop offset="1" stopColor={to} />
          </linearGradient>
        </defs>
        <rect width="280" height="120" fill={`url(#${gradient})`} />
        <Pattern kind={(n >> 4) % 4} seed={n} />
      </svg>
      <div className="relative h-full">{children}</div>
    </div>
  )
}
