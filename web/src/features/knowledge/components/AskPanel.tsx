import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../../components/ui/Button.tsx'
import { Card } from '../../../components/ui/Card.tsx'
import { Field, Textarea } from '../../../components/ui/Field.tsx'
import { ALL, Select } from '../../../components/ui/Select.tsx'
import { toast } from '../../../components/ui/Toast.tsx'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  type Answer, answer, type AnswerMode, categoryChoicesQuery, contextPack, type Pack,
} from '../api.ts'
import { AskResult } from './AskResult.tsx'

type Mode = 'pack' | 'project' | AnswerMode
const MODES: { value: Mode, label: () => string }[] = [
  { value: 'pack', label: () => m.ask_mode_pack() },
  { value: 'project', label: () => m.ask_mode_project() },
  { value: 'local', label: () => m.ask_mode_local() },
  { value: 'gemini', label: () => m.ask_mode_gemini() },
]

/** Ask the project's knowledge: the Context Pack alone, or a server-written answer. */
export function AskPanel({ projectId }: { projectId: string }) {
  const categories = useQuery(categoryChoicesQuery(projectId))
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [mode, setMode] = useState<Mode>('pack')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ pack: Pack, done: Answer | null } | null>(null)
  const cats = category ? [category] : []
  const run = async () => {
    setBusy(true)
    try {
      if (mode === 'pack') {
        setResult({ pack: await contextPack(projectId, query, cats), done: null })
      } else {
        const done = await answer(projectId, query, cats, mode === 'project' ? null : mode)
        setResult({ pack: done.pack, done })
      }
    } catch (error) {
      toast.error(m.ui_failed(), errorText(error))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <Card title={m.tab_ask()} description={m.ask_intro()}>
        <form className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); void run() }}>
          <Field label={m.ask_query()}>
            <Textarea rows={3} value={query} maxLength={2000} placeholder={m.ask_placeholder()}
              onChange={(e) => setQuery(e.target.value)} />
          </Field>
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <Field label={m.docs_category()}>
              <Select value={category || ALL} onChange={(v) => setCategory(v === ALL ? '' : v)}
                options={[{ value: ALL, label: m.ask_all_categories() },
                  ...(categories.data ?? []).map((c) => ({ value: c.id, label: c.name }))]} />
            </Field>
            <Field label={m.ask_mode()}>
              <Select value={mode} onChange={(v) => setMode(v as Mode)}
                options={MODES.map((x) => ({ value: x.value, label: x.label() }))} />
            </Field>
            <Button type="submit" loading={busy} disabled={query.trim() === ''}>
              {busy ? null : <Search />}{busy ? m.ask_running() : m.ask_submit()}
            </Button>
          </div>
        </form>
      </Card>
      {result ? <AskResult pack={result.pack} done={result.done} /> : null}
    </div>
  )
}
