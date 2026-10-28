import { Search } from 'lucide-react'
import { m } from '../../paraglide/messages.js'
import { Input } from './Field.tsx'

/** The search field of every list (tables and card grids alike). */
export function SearchBox({ value, onChange }: { value: string, onChange: (v: string) => void }) {
  return (
    <div className="relative w-full max-w-xs">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2
        text-muted-foreground" />
      <Input type="search" value={value} placeholder={m.ui_search()} aria-label={m.ui_search()}
        className="pl-8" onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

/** True when every word of `query` appears in one of `fields` (case-insensitive). */
export function matches(query: string, ...fields: (string | null | undefined)[]): boolean {
  const hay = fields.filter(Boolean).join(' ').toLowerCase()
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w))
}
