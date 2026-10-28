import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export type UserStatus = components['schemas']['UserStatus']

export const usersQuery = queryOptions({
  queryKey: ['admin', 'users'],
  queryFn: ({ signal }) => api('get', 'admin/users', { signal }),
})

export function createUser(email: string, password: string, displayName: string,
  groupIds: string[] = []) {
  return api('post', 'admin/users', { body: { email, password, display_name: displayName,
    system_role: 'user', group_ids: groupIds } })
}

/** Make these exactly the person's groups (they get each group's rights at once). */
export function setUserGroups(userId: string, groupIds: string[]) {
  return api('put', 'admin/users/{user_id}/groups',
    { path: { user_id: userId }, body: { group_ids: groupIds } })
}

export function setStatus(userId: string, status: UserStatus) {
  return api('patch', 'admin/users/{user_id}', { path: { user_id: userId }, body: { status } })
}

export function resetPassword(userId: string, password: string) {
  return api('post', 'admin/users/{user_id}/password',
    { path: { user_id: userId }, body: { password } })
}
