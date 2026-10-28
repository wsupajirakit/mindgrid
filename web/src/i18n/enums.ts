// Server enum values -> translated labels (explicit maps: each label is a real message).
import { m } from '../paraglide/messages.js'

const ROLE: Record<string, () => string> = {
  admin: () => m.role_admin(), editor: () => m.role_editor(), analyst: () => m.role_analyst(),
  viewer: () => m.role_viewer(), guest: () => m.role_guest(),
}
const LEVEL: Record<string, () => string> = {
  none: () => m.level_none(), read: () => m.level_read(), run: () => m.level_run(),
  edit: () => m.level_edit(), manage: () => m.level_manage(),
}
const SOURCE: Record<string, () => string> = {
  default: () => m.source_default(), system: () => m.source_system(), user: () => m.source_user(),
  project: () => m.source_project(), category: () => m.source_category(),
}

const TRUST: Record<string, () => string> = {
  unrated: () => m.trust_unrated(), verified: () => m.trust_verified(),
  claimed: () => m.trust_claimed(), disputed: () => m.trust_disputed(),
}
const RETRIEVER: Record<string, () => string> = {
  vector: () => m.retriever_vector(), keyword: () => m.retriever_keyword(),
  trigram: () => m.retriever_trigram(), rerank: () => m.retriever_rerank(),
}

const PLAYBOOK_STATUS: Record<string, () => string> = {
  draft: () => m.pb_status_draft(), provisional: () => m.pb_status_provisional(),
  active: () => m.pb_status_active(), paused: () => m.pb_status_paused(),
  retired: () => m.pb_status_retired(),
}
const RUN_STATUS: Record<string, () => string> = {
  queued: () => m.run_status_queued(), running: () => m.run_status_running(),
  done: () => m.run_status_done(), failed: () => m.run_status_failed(),
}

const DELIVERY: Record<string, () => string> = {
  pending: () => m.dl_pending(), sending: () => m.dl_sending(), delivered: () => m.dl_delivered(),
  dead: () => m.dl_dead(),
}

export const deliveryStatusText = (value: string) => DELIVERY[value]?.() ?? value
export const playbookStatusText = (value: string) => PLAYBOOK_STATUS[value]?.() ?? value
export const runStatusText = (value: string) => RUN_STATUS[value]?.() ?? value
export const trustText = (value: string) => TRUST[value]?.() ?? value
export const retrieverText = (value: string) => RETRIEVER[value]?.() ?? value
export const roleText = (value: string) => ROLE[value]?.() ?? value
export const levelText = (value: string) => LEVEL[value]?.() ?? value
export const sourceText = (value: string) => SOURCE[value]?.() ?? value
