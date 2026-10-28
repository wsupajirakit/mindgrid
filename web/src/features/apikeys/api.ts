import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export type KeyScope = components['schemas']['KeyScope']
export const SCOPES: readonly KeyScope[] = ['read', 'run', 'edit']

export const keysQuery = queryOptions({
  queryKey: ['admin', 'api-keys'],
  queryFn: ({ signal }) => api('get', 'admin/api-keys', { signal }),
})

export function issueKey(body: components['schemas']['NewKeyBody']) {
  return api('post', 'admin/api-keys', { body })
}

export function revokeKey(id: string) {
  return api('post', 'admin/api-keys/{key_uuid}/revoke', { path: { key_uuid: id } })
}

/** A new pair for the same owner, scopes and projects; the old key stops working at once. */
export function rotateKey(id: string) {
  return api('post', 'admin/api-keys/{key_uuid}/rotate', { path: { key_uuid: id } })
}
