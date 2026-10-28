import { infiniteQueryOptions } from '@tanstack/react-query'
import { appConfig } from '../../config/app.ts'
import { api } from '../../services/api/client.ts'

/** Newest first, one page at a time (the cursor is the last event id seen). */
export const auditQuery = (projectId?: string) => infiniteQueryOptions({
  queryKey: ['audit', projectId ?? 'all'],
  queryFn: ({ pageParam, signal }) => api('get', 'audit', {
    query: { project_id: projectId, before: pageParam, limit: appConfig.auditPageSize }, signal,
  }),
  initialPageParam: undefined as string | undefined,
  getNextPageParam: (page) =>
    page.length === appConfig.auditPageSize ? page[page.length - 1]?.id : undefined,
})

export type AuditEvent = Awaited<ReturnType<typeof api<'get', 'audit'>>>[number]
