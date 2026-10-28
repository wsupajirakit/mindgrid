import { createFileRoute } from '@tanstack/react-router'
import { ShieldCheck } from 'lucide-react'
import { Card } from '../../../components/ui/Card.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { SettingsPanel } from '../../../features/settings/components/SettingsPanel.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'

function SystemSettings() {
  useDocumentTitle(m.nav_system())
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<ShieldCheck />} title={m.settings_system()}
        description={m.settings_intro_system()} />
      <Card><SettingsPanel scope={{ kind: 'system' }} /></Card>
    </div>
  )
}

export const Route = createFileRoute('/_app/admin/settings')({ component: SystemSettings })
