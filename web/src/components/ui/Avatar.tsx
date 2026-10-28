// Account pictures: a built-in set drawn as SVG (no uploads, nothing fetched), or the
// initials on a colour derived from the name when none is chosen.
import { useId } from 'react'
import { cn } from '../../utils/cn.ts'

type Preset = { from: string, to: string, shape: 'rings' | 'waves' | 'grid' | 'orb' | 'peaks'
  | 'petals' }

const AVATARS: Record<string, Preset> = {
  aurora: { from: 'var(--av-aurora-a)', to: 'var(--av-aurora-b)', shape: 'waves' },
  sunset: { from: 'var(--av-sunset-a)', to: 'var(--av-sunset-b)', shape: 'orb' },
  ocean: { from: 'var(--av-ocean-a)', to: 'var(--av-ocean-b)', shape: 'rings' },
  forest: { from: 'var(--av-forest-a)', to: 'var(--av-forest-b)', shape: 'peaks' },
  orchid: { from: 'var(--av-orchid-a)', to: 'var(--av-orchid-b)', shape: 'petals' },
  ember: { from: 'var(--av-ember-a)', to: 'var(--av-ember-b)', shape: 'peaks' },
  lagoon: { from: 'var(--av-lagoon-a)', to: 'var(--av-lagoon-b)', shape: 'orb' },
  midnight: { from: 'var(--av-midnight-a)', to: 'var(--av-midnight-b)', shape: 'grid' },
  citrus: { from: 'var(--av-citrus-a)', to: 'var(--av-citrus-b)', shape: 'rings' },
  berry: { from: 'var(--av-berry-a)', to: 'var(--av-berry-b)', shape: 'waves' },
  glacier: { from: 'var(--av-glacier-a)', to: 'var(--av-glacier-b)', shape: 'grid' },
  dune: { from: 'var(--av-dune-a)', to: 'var(--av-dune-b)', shape: 'petals' },
}
export const AVATAR_IDS = Object.keys(AVATARS)

const SIZES = { sm: 'size-7 text-[11px]', md: 'size-9 text-xs', lg: 'size-14 text-base',
  xl: 'size-20 text-xl' }

function Shape({ shape }: { shape: Preset['shape'] }) {
  const ink = 'var(--ink-35)'
  switch (shape) {
    case 'rings':
      return <g fill="none" stroke={ink} strokeWidth="3">
        <circle cx="32" cy="32" r="10" /><circle cx="32" cy="32" r="18" />
        <circle cx="32" cy="32" r="26" /></g>
    case 'waves':
      return <g fill="none" stroke={ink} strokeWidth="3" strokeLinecap="round">
        <path d="M-4 24c10-8 20 8 30 0s20-8 30 0 12 6 16 2" />
        <path d="M-4 38c10-8 20 8 30 0s20-8 30 0 12 6 16 2" />
        <path d="M-4 52c10-8 20 8 30 0s20-8 30 0 12 6 16 2" /></g>
    case 'grid':
      return <g stroke={ink} strokeWidth="1.5">
        {[12, 24, 36, 48].map((v) => <line key={`h${v}`} x1="0" x2="64" y1={v} y2={v} />)}
        {[12, 24, 36, 48].map((v) => <line key={`v${v}`} y1="0" y2="64" x1={v} x2={v} />)}
        <circle cx="42" cy="22" r="7" fill={ink} /></g>
    case 'orb':
      return <g><circle cx="40" cy="24" r="16" fill={ink} />
        <circle cx="22" cy="44" r="9" fill="var(--ink-20)" /></g>
    case 'peaks':
      return <g><path d="M0 52 18 28l12 14 14-22 20 32v12H0z" fill={ink} />
        <circle cx="48" cy="14" r="5" fill="var(--ink-45)" /></g>
    case 'petals':
      return <g fill={ink}>
        {[0, 60, 120, 180, 240, 300].map((a) => (
          <ellipse key={a} cx="32" cy="18" rx="6" ry="13" transform={`rotate(${a} 32 32)`} />
        ))}<circle cx="32" cy="32" r="5" fill="var(--ink-60)" /></g>
  }
}

/** The picture itself (for the picker and anywhere a preset is shown). */
export function AvatarArt({ id, className }: { id: string, className?: string }) {
  const preset = AVATARS[id] ?? AVATARS.aurora!
  const gradient = `av-${useId().replace(/:/g, '')}`
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={preset.from} /><stop offset="1" stopColor={preset.to} />
        </linearGradient>
      </defs>
      <rect width="64" height="64" fill={`url(#${gradient})`} />
      <Shape shape={preset.shape} />
    </svg>
  )
}

function initials(name: string): string {
  const parts = name.replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts[1]?.[0] ?? '')).toUpperCase()
}

const HUES = [0, 1, 2, 3, 4, 5, 6].map((i) => `var(--hue-${String(i)})`)

function hue(name: string): string {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return HUES[h % HUES.length]!
}

export function Avatar({ name, avatar, size = 'md', className }: { name: string,
  avatar?: string, size?: keyof typeof SIZES, className?: string }) {
  const box = cn('relative shrink-0 overflow-hidden rounded-full ring-2 ring-background',
    SIZES[size], className)
  if (avatar && AVATARS[avatar]) {
    return <span className={box} title={name}><AvatarArt id={avatar} className="size-full" /></span>
  }
  return (
    <span className={cn(box, 'grid place-items-center font-semibold text-white')} title={name}>
      <svg viewBox="0 0 10 10" className="absolute inset-0 size-full" aria-hidden>
        <rect width="10" height="10" fill={hue(name)} />
      </svg>
      <span className="relative">{initials(name)}</span>
    </span>
  )
}
