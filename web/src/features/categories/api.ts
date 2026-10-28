import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export const categoriesQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'categories'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/categories',
    { path: { project_id: projectId }, signal }),
})

export function createCategory(projectId: string, slug: string, name: string,
  restricted: boolean) {
  return api('post', 'projects/{project_id}/categories',
    { path: { project_id: projectId }, body: { slug, name, restricted, description: '' } })
}

export type Category = Awaited<ReturnType<typeof api<'get',
  'projects/{project_id}/categories'>>>[number]
export type CategoryAccess = Awaited<ReturnType<typeof api<'get',
  'categories/{category_id}/access'>>>

/** Levels a grant can give, weakest first (0 = no grant). */
export const LEVELS = ['none', 'read', 'run', 'edit', 'manage'] as const
export type LevelName = (typeof LEVELS)[number]
const levelNumber = (name: LevelName) => LEVELS.indexOf(name) as 0 | 1 | 2 | 3 | 4

export const accessQuery = (categoryId: string) => queryOptions({
  queryKey: ['categories', categoryId, 'access'],
  queryFn: ({ signal }) => api('get', 'categories/{category_id}/access',
    { path: { category_id: categoryId }, signal }),
})

export function updateCategory(categoryId: string,
  change: { name?: string, description?: string, restricted?: boolean }) {
  return api('patch', 'categories/{category_id}',
    { path: { category_id: categoryId }, body: change })
}

export function setPersonGrant(categoryId: string, userId: string, level: LevelName) {
  return api('put', 'categories/{category_id}/grants/{user_id}',
    { path: { category_id: categoryId, user_id: userId }, body: { level: levelNumber(level) } })
}

export function setGroupGrant(categoryId: string, groupId: string, level: LevelName) {
  return api('put', 'categories/{category_id}/group-grants/{group_id}',
    { path: { category_id: categoryId, group_id: groupId }, body: { level: levelNumber(level) } })
}
