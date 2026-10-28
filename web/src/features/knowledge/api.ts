import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export type Trust = components['schemas']['Trust']
export type AnswerMode = 'none' | 'gemini' | 'local'
export const TRUST_VALUES: Trust[] = ['unrated', 'verified', 'claimed', 'disputed']

/** The same cache entry as the categories tab, so a new category shows up here too. */
export const categoryChoicesQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'categories'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/categories',
    { path: { project_id: projectId }, signal }),
})

export const documentsQuery = (categoryId: string) => queryOptions({
  queryKey: ['categories', categoryId, 'documents'],
  queryFn: ({ signal }) => api('get', 'categories/{category_id}/documents',
    { path: { category_id: categoryId }, signal }),
  enabled: categoryId !== '',
})

export const chunksQuery = (documentId: string) => queryOptions({
  queryKey: ['documents', documentId, 'chunks'],
  queryFn: ({ signal }) => api('get', 'documents/{document_id}/chunks',
    { path: { document_id: documentId }, query: { limit: 50 }, signal }),
})

export function uploadDocument(categoryId: string, file: File, title: string, trust: Trust) {
  const form = new FormData()
  form.set('file', file)
  form.set('title', title)
  form.set('trust', trust)
  return api('post', 'categories/{category_id}/documents',
    { path: { category_id: categoryId }, form })
}

export function setTrust(documentId: string, trust: Trust) {
  return api('put', 'documents/{document_id}/trust',
    { path: { document_id: documentId }, body: { trust } })
}

export function removeDocument(documentId: string) {
  return api('delete', 'documents/{document_id}', { path: { document_id: documentId } })
}

export function contextPack(projectId: string, query: string, categories: string[]) {
  return api('post', 'projects/{project_id}/context-pack',
    { path: { project_id: projectId }, body: { query, categories, k: 0 } })
}

export function answer(projectId: string, query: string, categories: string[],
  llm: AnswerMode | null) {
  return api('post', 'projects/{project_id}/answer',
    { path: { project_id: projectId }, body: { query, categories, k: 0, llm } })
}

export type Pack = Awaited<ReturnType<typeof contextPack>>
export type Answer = Awaited<ReturnType<typeof answer>>

export const graphQuery = (projectId: string) => queryOptions({
  queryKey: ['knowledge', 'graph', projectId],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/knowledge-graph',
    { path: { project_id: projectId }, signal }),
})

export type GraphNode = { id: string, kind: 'project' | 'category' | 'document', label: string,
  chunks?: number, trust?: string, category_id?: string, restricted?: boolean }
export type GraphEdge = { source: string, target: string, kind: 'contains' | 'together',
  weight?: number }
