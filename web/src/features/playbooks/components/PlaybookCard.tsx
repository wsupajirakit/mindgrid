import { Play, Workflow } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button, type Variant } from '../../../components/ui/Button.tsx'
import { CoverCard } from '../../../components/ui/CoverCard.tsx'
import { Tooltip } from '../../../components/ui/Tooltip.tsx'
import { playbookStatusText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import type { PlaybookRow } from '../api.ts'
import { localized } from '../localized.ts'

function Facts({ label, items }: { label: string, items: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs">
      <span className="mr-1 text-muted-foreground">{label}</span>
      {items.length === 0 ? <span className="text-muted-foreground">{m.pb_none()}</span>
        : items.map((item) => <Badge key={item} tone="outline">{item}</Badge>)}
    </div>
  )
}

/** A card button: icon and text, or (compact) the icon alone with the text as tooltip. */
export function CardAction({ icon, label, onClick, compact, variant = 'outline',
  className }: { icon: ReactNode, label: string, onClick: () => void, compact: boolean,
  variant?: Variant, className?: string }) {
  if (!compact) {
    return <Button variant={variant} size="sm" className={className} onClick={onClick}>
      {icon}{label}</Button>
  }
  return (
    <Tooltip text={label} side="top">
      <Button variant={variant} size="icon-sm" className={className} aria-label={label}
        onClick={onClick}>{icon}</Button>
    </Tooltip>
  )
}

/** One playbook: cover, what it does (in the interface language when translated), what it
 * takes; `footer` holds the controls the page allows, `onRun` adds a run button. `compact`
 * (dense grids) clamps the text and shows counts instead of the chip rows. */
export function PlaybookCard({ playbook, footer, onRun, compact = false }: {
  playbook: PlaybookRow, footer?: ReactNode, onRun?: () => void, compact?: boolean }) {
  const functions = [...new Set(playbook.functions ?? [])]
  const text = localized(playbook)
  const steps = String(playbook.functions?.length ?? 0)
  return (
    <CoverCard seed={playbook.id} icon={<Workflow />} title={text.title} compact={compact}
      subtitle={playbook.id} badges={(
        <>
          <Badge className="bg-black/30 text-white uppercase" >{text.locale}</Badge>
          {playbook.versions.map((v) => (
            <Badge key={v.version} className="bg-black/30 text-white">
              {compact ? `v${String(v.version)}`
                : `v${String(v.version)} · ${playbookStatusText(v.status)}`}
            </Badge>
          ))}
        </>
      )} actions={(
        <>
          {footer}
          <span className="flex-1" />
          {onRun ? (
            <CardAction variant="default" icon={<Play />} label={m.pb_run()} onClick={onRun}
              compact={compact} />
          ) : null}
        </>
      )}>
      {text.summary ? (
        <p className={compact ? 'line-clamp-2 text-xs text-muted-foreground'
          : 'line-clamp-3 text-sm text-muted-foreground'}>{text.summary}</p>
      ) : null}
      {compact ? (
        <p className="text-[11px] text-muted-foreground">
          {m.pb_counts({ inputs: String(playbook.inputs?.length ?? 0),
            params: String(playbook.param_names?.length ?? 0), steps })}
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-1.5">
            <Facts label={m.pb_inputs()} items={playbook.inputs ?? []} />
            <Facts label={m.pb_params()} items={playbook.param_names ?? []} />
            <Facts label={m.pb_functions()} items={functions} />
          </div>
          <p className="text-xs text-muted-foreground">{m.pb_steps_n({ n: steps })}</p>
        </>
      )}
    </CoverCard>
  )
}
