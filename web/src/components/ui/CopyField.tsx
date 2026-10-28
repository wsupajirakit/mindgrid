import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { m } from '../../paraglide/messages.js'
import { Button } from './Button.tsx'

/** Read-only text (a key, a secret shown once) with a copy button. */
export function CopyField({ value, rows = 4, label }: { value: string, rows?: number,
  label: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="relative">
      <textarea readOnly rows={rows} value={value} aria-label={label}
        className="w-full resize-none rounded-lg border border-border bg-muted p-3 pr-12
          font-mono text-xs" />
      <Button variant="outline" size="icon-sm" className="absolute top-2 right-2"
        aria-label={copied ? m.ui_copied() : m.ui_copy()} onClick={() => void copy()}>
        {copied ? <Check /> : <Copy />}
      </Button>
    </div>
  )
}
