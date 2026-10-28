import { Check } from 'lucide-react'
import { Checkbox as RadixCheckbox, Switch as RadixSwitch } from 'radix-ui'
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'
import { cn } from '../../utils/cn.ts'

export const controlClass = 'w-full rounded-md border border-input bg-card px-3 py-2 '
  + 'text-sm shadow-sm transition-colors placeholder:text-muted-foreground '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring '
  + 'disabled:cursor-not-allowed disabled:opacity-50'

/** Label + control, then a hint or error (outside the label, so the control's name is the
 * label alone). */
export function Field({ label, hint, error, className, children }: { label: ReactNode,
  hint?: ReactNode, error?: string, className?: string, children: ReactNode }) {
  return (
    <div className={cn('flex flex-col gap-1.5 text-sm', className)}>
      <label className="flex flex-col gap-1.5">
        <span className="font-medium">{label}</span>
        {children}
      </label>
      {error ? <span role="alert" className="text-xs text-destructive">{error}</span>
        : hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </div>
  )
}

/** A titled set of controls (checkboxes, radios): a fieldset with a legend, so each control
 * keeps its own name instead of sitting inside one label. */
export function FieldGroup({ label, hint, className, children }: { label: ReactNode,
  hint?: ReactNode, className?: string, children: ReactNode }) {
  return (
    <fieldset className={cn('flex flex-col gap-1.5 text-sm', className)}>
      <legend className="mb-1.5 font-medium">{label}</legend>
      {children}
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </fieldset>
  )
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlClass, 'h-9', className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(controlClass, 'min-h-20', className)} {...props} />
}

export function Checkbox({ checked, onChange, label, id }: { checked: boolean,
  onChange: (value: boolean) => void, label: ReactNode, id?: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <RadixCheckbox.Root id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)}
        className="grid size-4 place-items-center rounded-[4px] border border-input bg-card
          data-[state=checked]:border-primary data-[state=checked]:bg-primary
          data-[state=checked]:text-primary-foreground">
        <RadixCheckbox.Indicator><Check className="size-3" /></RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      {label}
    </label>
  )
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean,
  onChange: (value: boolean) => void, label: string, disabled?: boolean }) {
  return (
    <RadixSwitch.Root checked={checked} onCheckedChange={onChange} aria-label={label}
      disabled={disabled}
      className="inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2
        border-transparent bg-input transition-colors data-[state=checked]:bg-primary
        disabled:opacity-50">
      <RadixSwitch.Thumb className="block size-4 rounded-full bg-background shadow
        transition-transform data-[state=checked]:translate-x-4" />
    </RadixSwitch.Root>
  )
}
