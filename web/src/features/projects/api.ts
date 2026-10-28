import { queryOptions } from '@tanstack/react-query'
import { appConfig } from '../../config/app.ts'
import { api } from '../../services/api/client.ts'

export const projectsQuery = (archived = false) => queryOptions({
  queryKey: ['projects', { archived }],
  queryFn: ({ signal }) => api('get', 'projects', { query: { archived }, signal }),
  staleTime: appConfig.staleTime.list,
})

export const projectQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}',
    { path: { project_id: projectId }, signal }),
})

export function createProject(slug: string, name: string, description: string) {
  return api('post', 'projects', { body: { slug, name, description } })
}

export function deleteProject(projectId: string) {
  return api('delete', 'projects/{project_id}', { path: { project_id: projectId } })
}

/** The project's categories (for choosing what to copy). */
export const projectCategoriesQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'categories'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/categories',
    { path: { project_id: projectId }, signal }),
})

/** Superadmin: copy categories (with documents) and the playbook choices to another project. */
export function copyProject(projectId: string, target: string, categoryIds: string[],
  playbooks: boolean) {
  return api('post', 'admin/projects/{project_id}/copy', { path: { project_id: projectId },
    body: { target_project_id: target, category_ids: categoryIds, playbooks } })
}
