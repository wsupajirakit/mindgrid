import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export const datasetsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'datasets'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/datasets',
    { path: { project_id: projectId }, signal }),
})

export const versionsQuery = (projectId: string, name: string) => queryOptions({
  queryKey: ['projects', projectId, 'datasets', name, 'versions'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/datasets/{name}/versions',
    { path: { project_id: projectId, name }, signal }),
})

export const rowsQuery = (projectId: string, name: string) => queryOptions({
  queryKey: ['projects', projectId, 'datasets', name, 'rows'],
  queryFn: async ({ signal }) => (await api('get', 'projects/{project_id}/datasets/{name}/rows',
    { path: { project_id: projectId, name }, query: { limit: 20 }, signal })) as {
      items: Record<string, unknown>[], columns: string[], rows: number },
})

export const connectorsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'connectors'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/connectors',
    { path: { project_id: projectId }, signal }),
})

export const templatesQuery = queryOptions({
  queryKey: ['connector-templates'],
  queryFn: async ({ signal }) => (await api('get', 'connector-templates', { signal })) as {
    id: string, title: string, summary: string, spec: Record<string, unknown>,
    every_minutes: number | null }[],
  staleTime: Infinity,
})

export function saveConnector(projectId: string, name: string, spec: unknown,
  every: number | null) {
  return api('put', 'projects/{project_id}/connectors/{name}', {
    path: { project_id: projectId, name },
    body: { spec: spec as never, every_minutes: every },
  })
}

export function syncConnector(id: string) {
  return api('post', 'connectors/{connector_id}/sync', { path: { connector_id: id } })
}

/** Dataset names the server accepts (mirrors `datasets.models.NAME`). */
export const DATASET_NAME = /^[a-z0-9][a-z0-9_.-]{0,99}$/
export const FORMATS = ['csv', 'json', 'ndjson'] as const
export type Format = (typeof FORMATS)[number]

export function uploadDataset(projectId: string, name: string, file: File, format: Format,
  recordsPath: string) {
  const form = new FormData()
  form.set('file', file)
  form.set('format', format)
  form.set('records_path', recordsPath)
  return api('post', 'projects/{project_id}/datasets/{name}',
    { path: { project_id: projectId, name }, form })
}

export type ConnectorRow = Awaited<ReturnType<typeof api<'get',
  'projects/{project_id}/connectors'>>>[number]
