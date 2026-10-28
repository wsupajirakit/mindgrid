import { Lightbulb, Settings2, Target } from 'lucide-react'
import type { ReactNode } from 'react'
import { m } from '../../../paraglide/messages.js'

function Point({ icon, title, text }: { icon: ReactNode, title: string, text: string }) {
  return (
    <div className="flex gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent
        text-accent-foreground [&_svg]:size-4">{icon}</span>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{text}</p>
      </div>
    </div>
  )
}

/** What a playbook is, how it runs, what it is for. */
export function PlaybooksIntro() {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Point icon={<Lightbulb />} title={m.pb_what_title()} text={m.pb_what_text()} />
      <Point icon={<Settings2 />} title={m.pb_how_title()} text={m.pb_how_text()} />
      <Point icon={<Target />} title={m.pb_use_title()} text={m.pb_use_text()} />
    </div>
  )
}
