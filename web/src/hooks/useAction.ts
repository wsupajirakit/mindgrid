// Runs a change and tells the outcome in a toast: success text on success (a function when
// the text depends on the result), the translated server error otherwise. Returns true when
// the change went through.
import { useState } from 'react'
import { toast } from '../components/ui/Toast.tsx'
import { m } from '../paraglide/messages.js'
import { errorText } from '../services/api/errorMessages.ts'

export function useAction() {
  const [busy, setBusy] = useState(false)
  const run = async (work: () => Promise<unknown>,
    success: string | (() => string) = m.ui_saved()) => {
    setBusy(true)
    try {
      await work()
      toast.success(typeof success === 'function' ? success() : success)
      return true
    } catch (error) {
      toast.error(m.ui_failed(), error instanceof SyntaxError ? m.ui_bad_json()
        : errorText(error))
      return false
    } finally {
      setBusy(false)
    }
  }
  return { busy, run }
}
