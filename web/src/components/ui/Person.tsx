import type { ReactNode } from 'react'
import { Avatar } from './Avatar.tsx'

export type PersonInfo = { name: string, email: string, avatar?: string }

/** Who someone is: avatar, name and email (never a bare user id); `fallback` when the
 * person is unknown or not visible to the viewer. */
export function Person({ person, fallback }: { person: PersonInfo | null | undefined,
  fallback: ReactNode }) {
  if (!person) return <span className="text-muted-foreground">{fallback}</span>
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <Avatar name={person.name} avatar={person.avatar} size="sm" />
      <span className="min-w-0 leading-tight">
        <span className="block truncate font-medium">{person.name}</span>
        <span className="block truncate text-xs text-muted-foreground">{person.email}</span>
      </span>
    </span>
  )
}
