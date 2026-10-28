import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export type ParamSpec = { type: string, default?: unknown, minimum?: number | null,
  maximum?: number | null, choices?: unknown[] | null, doc?: string }
export type Spec = { id: string, version: number, status: string, title: string,
  summary: string, params: Record<string, ParamSpec>,
  inputs: Record<string, { type: string, required?: boolean, doc?: string }> }

export const playbooksQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'playbooks'],
  queryFn: ({ signal }) => api('get', 'playbooks', { query: { project_id: projectId }, signal }),
})

export const specQuery = (id: string, version: number) => queryOptions({
  queryKey: ['playbooks', id, version],
  queryFn: async ({ signal }) => (await api('get', 'playbooks/{playbook_id}/versions/{version}',
    { path: { playbook_id: id, version }, signal })) as unknown as Spec,
})

export const runsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'runs'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/runs',
    { path: { project_id: projectId }, signal }),
  refetchInterval: (q) => q.state.data?.some((r) => r.status === 'queued' || r.status === 'running')
    ? 2000 : false,
})

export function setEnabled(projectId: string, playbookId: string, enabled: boolean,
  params: Record<string, unknown>, version: number | null) {
  return api('put', 'projects/{project_id}/playbooks/{playbook_id}', {
    path: { project_id: projectId, playbook_id: playbookId },
    body: { enabled, params, version },
  })
}

export function startRun(projectId: string, playbook: string, version: number,
  params: Record<string, unknown>, inputs: Record<string, unknown>) {
  return api('post', 'projects/{project_id}/runs', {
    path: { project_id: projectId },
    body: { playbook, version, params, inputs, wait_seconds: 10 },
  })
}

export type RunRow = Awaited<ReturnType<typeof startRun>>
export type PlaybookRow = Awaited<ReturnType<typeof api<'get', 'playbooks'>>>[number]

export const playbookCatalogQuery = queryOptions({
  queryKey: ['playbooks', 'system'],
  queryFn: ({ signal }) => api('get', 'playbooks', { signal }),
})

/** Switch a playbook on or off for every project (a project override still wins). */
export function setSystemPlaybook(playbookId: string, enabled: boolean) {
  return api('put', 'admin/playbooks/{playbook_id}/override',
    { path: { playbook_id: playbookId }, body: { enabled, params: {}, version: null } })
}

export function addCustomPlaybook(spec: unknown) {
  return api('post', 'admin/playbooks', { body: spec as never })
}

export const runQuery = (id: string) => queryOptions({
  queryKey: ['runs', id],
  queryFn: ({ signal }) => api('get', 'runs/{run_id}', { path: { run_id: id }, signal }),
  refetchInterval: (q) => q.state.data?.status === 'queued' || q.state.data?.status === 'running'
    ? 2000 : false,
})

export type Assignments = Awaited<ReturnType<typeof api<'get',
  'playbooks/{playbook_id}/assignments'>>>

export const assignmentsQuery = (playbookId: string) => queryOptions({
  queryKey: ['playbooks', playbookId, 'assignments'],
  queryFn: ({ signal }) => api('get', 'playbooks/{playbook_id}/assignments',
    { path: { playbook_id: playbookId }, signal }),
})

export function saveAssignments(playbookId: string, allProjects: boolean | null,
  projects: Record<string, boolean>) {
  return api('put', 'playbooks/{playbook_id}/assignments', {
    path: { playbook_id: playbookId },
    body: { all_projects: allProjects, projects },
  })
}

export function saveTranslation(playbookId: string, locale: string, title: string,
  summary: string) {
  return title.trim()
    ? api('put', 'admin/playbooks/{playbook_id}/translations/{locale}',
      { path: { playbook_id: playbookId, locale }, body: { title, summary } })
    : api('delete', 'admin/playbooks/{playbook_id}/translations/{locale}',
      { path: { playbook_id: playbookId, locale } })
}
