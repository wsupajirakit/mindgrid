import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

/** Where a settings or secrets panel acts: the system, me, a project or a category. */
export type SettingsScope =
  | { kind: 'system' } | { kind: 'me' }
  | { kind: 'project', id: string } | { kind: 'category', id: string }

const key = (scope: SettingsScope) => ['settings', scope.kind, 'id' in scope ? scope.id : '']

export const settingsQuery = (scope: SettingsScope) => queryOptions({
  queryKey: key(scope),
  queryFn: ({ signal }) => {
    switch (scope.kind) {
      case 'system': return api('get', 'admin/settings', { signal })
      case 'me': return api('get', 'me/settings', { signal })
      case 'project': return api('get', 'projects/{project_id}/settings',
        { path: { project_id: scope.id }, signal })
      case 'category': return api('get', 'categories/{category_id}/settings',
        { path: { category_id: scope.id }, signal })
    }
  },
})

export function putSetting(scope: SettingsScope, settingKey: string, value: unknown) {
  const body = { value }
  switch (scope.kind) {
    case 'system': return api('put', 'admin/settings/{key}', { path: { key: settingKey }, body })
    case 'me': return api('put', 'me/settings/{key}', { path: { key: settingKey }, body })
    case 'project': return api('put', 'projects/{project_id}/settings/{key}',
      { path: { project_id: scope.id, key: settingKey }, body })
    case 'category': return api('put', 'categories/{category_id}/settings/{key}',
      { path: { category_id: scope.id, key: settingKey }, body })
  }
}

export const secretsQuery = (projectId: string) => queryOptions({
  queryKey: ['secrets', projectId],
  queryFn: ({ signal }) => api('get', 'projects/{scope_id}/secrets',
    { path: { scope_id: projectId }, signal }),
})

export function putSecret(projectId: string, name: string, value: string) {
  return api('put', 'projects/{scope_id}/secrets/{name}',
    { path: { scope_id: projectId, name }, body: { value } })
}

export function removeSecret(projectId: string, name: string) {
  return api('delete', 'projects/{scope_id}/secrets/{name}',
    { path: { scope_id: projectId, name } })
}
