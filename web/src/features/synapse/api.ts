import { queryOptions } from '@tanstack/react-query'
import { api, apiHref } from '../../services/api/client.ts'

export const sourcesQuery = queryOptions({
  queryKey: ['synapse', 'sources'],
  queryFn: ({ signal }) => api('get', 'admin/synapse/sources', { signal }),
})

export const proposalsQuery = queryOptions({
  queryKey: ['synapse', 'proposals'],
  queryFn: ({ signal }) => api('get', 'synapse/proposals', { signal }),
  refetchInterval: 10_000,
})

export const templatesQuery = queryOptions({
  queryKey: ['synapse', 'templates'],
  queryFn: async ({ signal }) => (await api('get', 'synapse/templates', { signal })) as {
    id: string, title: string, mapping: Record<string, unknown> }[],
  staleTime: Infinity,
})

export function addSource(body: { name: string, path: string, mapping: unknown,
  project_id: string, category_id: string, every_minutes: number | null }) {
  return api('post', 'admin/synapse/sources', { body: body as never })
}

export function check(id: string, importAll: boolean) {
  return api('post', 'admin/synapse/sources/{source_id}/check',
    { path: { source_id: id }, body: { import_all: importAll } })
}

export function decide(proposalId: string, index: number, accept: boolean) {
  return api('post', 'synapse/proposals/{proposal_id}/items/{index}',
    { path: { proposal_id: proposalId, index }, body: { accept } })
}

export type Proposal = Awaited<ReturnType<typeof api<'get', 'synapse/proposals'>>>[number]

export const tasksHref = (proposalId: string) => apiHref(`synapse/proposals/${proposalId}/tasks.md`)
export type Source = Awaited<ReturnType<typeof api<'get', 'admin/synapse/sources'>>>[number]
