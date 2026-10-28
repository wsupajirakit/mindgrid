import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export type ProjectRole = components['schemas']['ProjectRole']
export const ROLES: readonly ProjectRole[] = ['admin', 'editor', 'analyst', 'viewer', 'guest']

export const membersQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'members'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/members',
    { path: { project_id: projectId }, signal }),
})

export function inviteMember(projectId: string, email: string, role: ProjectRole) {
  return api('post', 'projects/{project_id}/members',
    { path: { project_id: projectId }, body: { email, role } })
}

export function setRole(projectId: string, userId: string, role: ProjectRole) {
  return api('put', 'projects/{project_id}/members/{user_id}',
    { path: { project_id: projectId, user_id: userId }, body: { role } })
}

export function removeMember(projectId: string, userId: string) {
  return api('delete', 'projects/{project_id}/members/{user_id}',
    { path: { project_id: projectId, user_id: userId } })
}

export type Person = Awaited<ReturnType<typeof api<'get', 'projects/{project_id}/people'>>>[number]
export type GroupRole = Awaited<ReturnType<typeof api<'get',
  'projects/{project_id}/groups'>>>[number]

/** Everyone with a role here and where it comes from (own, or via groups). */
export const peopleQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'people'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/people',
    { path: { project_id: projectId }, signal }),
})

export const projectGroupsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'groups'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/groups',
    { path: { project_id: projectId }, signal }),
})

export function setGroupRole(projectId: string, groupId: string, role: ProjectRole) {
  return api('put', 'projects/{project_id}/groups/{group_id}',
    { path: { project_id: projectId, group_id: groupId }, body: { role } })
}

export function removeGroupRole(projectId: string, groupId: string) {
  return api('delete', 'projects/{project_id}/groups/{group_id}',
    { path: { project_id: projectId, group_id: groupId } })
}
