import { createFileRoute } from '@tanstack/react-router'
import { ScrollText } from 'lucide-react'
import { Card } from '../../components/ui/Card.tsx'
import { PageHeader } from '../../components/ui/PageHeader.tsx'
import { AuditLog } from '../../features/audit/components/AuditLog.tsx'
import { useDocumentTitle } from '../../hooks/useBrand.ts'
import { m } from '../../paraglide/messages.js'

function Logs() {
  useDocumentTitle(m.nav_logs())
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<ScrollText />} title={m.logs_title()} description={m.logs_intro()} />
      <Card><AuditLog /></Card>
    </div>
  )
}

export const Route = createFileRoute('/_app/logs')({ component: Logs })
