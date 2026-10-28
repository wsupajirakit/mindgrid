import { useQuery } from '@tanstack/react-query'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { chunksQuery } from '../api.ts'

/** A document's passages, as the knowledge base holds them. */
export function DocumentPreview({ documentId, onClose }: { documentId: string,
  onClose: () => void }) {
  const chunks = useQuery(chunksQuery(documentId))
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="xl"
      title={m.docs_preview_title()}
      description={chunks.data ? m.net_chunks({ n: String(chunks.data.length) }) : undefined}>
      {chunks.error ? <Notice tone="error">{errorText(chunks.error)}</Notice>
        : !chunks.data ? <Skeleton className="h-60" /> : (
          <ol className="flex flex-col gap-3">
            {chunks.data.map((c) => (
              <li key={c.ordinal} className="rounded-lg border border-border p-4 text-sm">
                {c.heading ? <p className="mb-2 font-semibold text-primary">{c.heading}</p> : null}
                <p className="whitespace-pre-wrap leading-relaxed text-muted-foreground">
                  {c.text}
                </p>
              </li>
            ))}
          </ol>
        )}
    </Modal>
  )
}
