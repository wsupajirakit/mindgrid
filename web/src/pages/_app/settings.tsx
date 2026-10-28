import { createFileRoute } from '@tanstack/react-router'
import { Settings } from 'lucide-react'
import { Card } from '../../components/ui/Card.tsx'
import { PageHeader } from '../../components/ui/PageHeader.tsx'
import { SettingsPanel } from '../../features/settings/components/SettingsPanel.tsx'
import { useDocumentTitle } from '../../hooks/useBrand.ts'
import { m } from '../../paraglide/messages.js'

function MySettings() {
  useDocumentTitle(m.nav_settings())
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<Settings />} title={m.settings_mine()}
        description={m.settings_intro_mine()} />
      <Card><SettingsPanel scope={{ kind: 'me' }} /></Card>
    </div>
  )
}

export const Route = createFileRoute('/_app/settings')({ component: MySettings })
