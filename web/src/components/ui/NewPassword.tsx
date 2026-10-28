import { Check, X } from 'lucide-react'
import { m } from '../../paraglide/messages.js'
import { cn } from '../../utils/cn.ts'
import { MIN_LENGTH, passwordChecks, type Rule, RULES } from '../../utils/passwordRules.ts'
import { Field, Input } from './Field.tsx'

const LABEL: Record<Rule, () => string> = {
  length: () => m.pw_rule_length({ min: String(MIN_LENGTH) }),
  lower: () => m.pw_rule_lower(),
  upper: () => m.pw_rule_upper(),
  digit: () => m.pw_rule_digit(),
}

/** Each rule ticks as it is met, so the person sees what is still missing. */
function RuleList({ password }: { password: string }) {
  const checks = passwordChecks(password)
  return (
    <div className="rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-xs">
      <ul aria-label={m.pw_rules()} className="grid gap-1.5 sm:grid-cols-2">
        {RULES.map((r) => (
          <li key={r} className={cn('flex items-center gap-1.5 transition-colors',
            checks[r] ? 'text-[var(--status-good)]' : 'text-muted-foreground')}>
            <span aria-hidden className={cn('grid size-4 shrink-0 place-items-center rounded-full',
              '[&_svg]:size-3', checks[r] ? 'bg-[var(--status-good)]/15' : 'bg-muted')}>
              {checks[r] ? <Check /> : <X />}
            </span>
            <span>{LABEL[r]()}</span>
            <span className="sr-only">
              {checks[r] ? m.pw_rule_met() : m.pw_rule_needed()}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-muted-foreground">{m.pw_rule_symbols()}</p>
    </div>
  )
}

/** A new password typed twice, with the rules shown live. Send only when
 * `passwordReady(value, repeat)` holds. */
export function NewPassword({ value, repeat, onChange, onRepeatChange, label, repeatLabel,
  autoFocus }: { value: string, repeat: string, onChange: (value: string) => void,
  onRepeatChange: (value: string) => void, label?: string, repeatLabel?: string,
  autoFocus?: boolean }) {
  const mismatch = repeat !== '' && value !== repeat
  return (
    <div className="flex flex-col gap-3">
      <Field label={label ?? m.field_password()}>
        <Input type="password" autoComplete="new-password" value={value} autoFocus={autoFocus}
          onChange={(e) => onChange(e.target.value)} />
      </Field>
      <RuleList password={value} />
      <Field label={repeatLabel ?? m.pw_repeat()} error={mismatch ? m.pw_mismatch() : undefined}>
        <Input type="password" autoComplete="new-password" value={repeat}
          aria-invalid={mismatch || undefined} onChange={(e) => onRepeatChange(e.target.value)} />
      </Field>
    </div>
  )
}
