// System-wide event receivers (every project): superadmin only.
import { createFileRoute } from '@tanstack/react-router'
import { Radio } from 'lucide-react'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { EventsPanel } from '../../../features/events/components/EventsPanel.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'

function SystemEvents() {
  useDocumentTitle(m.nav_events())
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<Radio />} title={m.nav_events()} description={m.ev_system_intro()} />
      <EventsPanel projectId={null} />
    </div>
  )
}

export const Route = createFileRoute('/_app/admin/events')({ component: SystemEvents })
