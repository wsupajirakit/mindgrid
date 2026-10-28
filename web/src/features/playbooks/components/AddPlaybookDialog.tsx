import { useQueryClient } from '@tanstack/react-query'
import { Workflow } from 'lucide-react'
import { useState } from 'react'
import { FormModal } from '../../../components/ui/Dialog.tsx'
import { Checkbox } from '../../../components/ui/Field.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { m } from '../../../paraglide/messages.js'
import { type PlaybookRow, playbooksQuery, setEnabled } from '../api.ts'
import { localized } from '../localized.ts'

/** Pick playbooks from the catalog to switch on in this project. */
export function AddPlaybookDialog({ projectId, available, onClose }: { projectId: string,
  available: PlaybookRow[], onClose: () => void }) {
  const queryClient = useQueryClient()
  const { busy, run } = useAction()
  const [picked, setPicked] = useState<string[]>([])
  const save = async () => {
    const ok = await run(async () => {
      for (const p of available.filter((x) => picked.includes(x.id))) {
        await setEnabled(projectId, p.id, true, p.params, p.pinned_version)
      }
      await queryClient.invalidateQueries({ queryKey: playbooksQuery(projectId).queryKey })
    }, m.pb_added())
    if (ok) onClose()
  }
  return (
    <FormModal open onOpenChange={(o) => { if (!o) onClose() }} size="lg" title={m.pb_add()}
      description={m.pb_add_hint()} submitLabel={m.action_add()} busy={busy}
      disabled={picked.length === 0} onSubmit={save}>
      {available.length === 0 ? <Notice>{m.pb_all_added()}</Notice> : (
        <ul className="flex flex-col gap-2">
          {available.map((p) => {
            const text = localized(p)
            return (
              <li key={p.id} className="flex items-start gap-3 rounded-lg border border-border p-3">
                <Checkbox checked={picked.includes(p.id)} label={(
                  <span className="flex items-center gap-2 font-medium">
                    <Workflow className="size-4 text-primary" />{text.title}
                  </span>
                )} onChange={(on) => setPicked(on ? [...picked, p.id]
                  : picked.filter((x) => x !== p.id))} />
                <p className="line-clamp-2 flex-1 text-xs text-muted-foreground">{text.summary}</p>
              </li>
            )
          })}
        </ul>
      )}
    </FormModal>
  )
}
