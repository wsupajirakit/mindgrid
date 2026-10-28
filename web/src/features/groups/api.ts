import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export type Group = Awaited<ReturnType<typeof api<'get', 'groups'>>>[number]
export type GroupMember = Awaited<ReturnType<typeof api<'get',
  'admin/groups/{group_id}/members'>>>[number]

/** Every group (anyone signed in may list them, to pick one). */
export const groupsQuery = queryOptions({
  queryKey: ['groups'],
  queryFn: ({ signal }) => api('get', 'groups', { signal }),
})

export const groupMembersQuery = (groupId: string) => queryOptions({
  queryKey: ['groups', groupId, 'members'],
  queryFn: ({ signal }) => api('get', 'admin/groups/{group_id}/members',
    { path: { group_id: groupId }, signal }),
})

export function createGroup(name: string, description: string) {
  return api('post', 'admin/groups', { body: { name, description } })
}

export function updateGroup(groupId: string, name: string, description: string) {
  return api('patch', 'admin/groups/{group_id}',
    { path: { group_id: groupId }, body: { name, description } })
}

export function deleteGroup(groupId: string) {
  return api('delete', 'admin/groups/{group_id}', { path: { group_id: groupId } })
}

export function addGroupMember(groupId: string, userId: string) {
  return api('put', 'admin/groups/{group_id}/members/{user_id}',
    { path: { group_id: groupId, user_id: userId } })
}

export function removeGroupMember(groupId: string, userId: string) {
  return api('delete', 'admin/groups/{group_id}/members/{user_id}',
    { path: { group_id: groupId, user_id: userId } })
}
