import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export type Scope = { projectId: string | null }  // null = system-wide (superadmin)

export const typesQuery = queryOptions({
  queryKey: ['event-types'],
  queryFn: ({ signal }) => api('get', 'events/types', { signal }),
  staleTime: Infinity,
})

export const subscriptionsQuery = ({ projectId }: Scope) => queryOptions({
  queryKey: ['event-subscriptions', projectId ?? 'system'],
  queryFn: ({ signal }) => projectId
    ? api('get', 'projects/{project_id}/event-subscriptions',
      { path: { project_id: projectId }, signal })
    : api('get', 'admin/event-subscriptions', { signal }),
})

export const deliveriesQuery = (subscriptionId: string) => queryOptions({
  queryKey: ['event-deliveries', subscriptionId],
  queryFn: ({ signal }) => api('get', 'event-subscriptions/{subscription_id}/deliveries',
    { path: { subscription_id: subscriptionId }, signal }),
  refetchInterval: 3000,
})

export const eventsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'events'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/events',
    { path: { project_id: projectId }, query: { limit: 50 }, signal }),
  refetchInterval: 5000,
})

export function subscribe({ projectId }: Scope, name: string, url: string, types: string[]) {
  const body = { name, url, event_types: types }
  return projectId
    ? api('post', 'projects/{project_id}/event-subscriptions',
      { path: { project_id: projectId }, body })
    : api('post', 'admin/event-subscriptions', { body })
}

export function setEnabled(id: string, enabled: boolean) {
  return api('patch', 'event-subscriptions/{subscription_id}',
    { path: { subscription_id: id }, body: { enabled } })
}

export function remove(id: string) {
  return api('delete', 'event-subscriptions/{subscription_id}', { path: { subscription_id: id } })
}

export function ping(id: string) {
  return api('post', 'event-subscriptions/{subscription_id}/test',
    { path: { subscription_id: id } })
}

export function replay(id: string) {
  return api('post', 'event-deliveries/{delivery_id}/replay', { path: { delivery_id: id } })
}

export type Subscription = Awaited<ReturnType<typeof subscribe>>['subscription']
export type Delivery = Awaited<ReturnType<typeof api<'get',
  'event-subscriptions/{subscription_id}/deliveries'>>>[number]
export type EventRow = Awaited<ReturnType<typeof api<'get',
  'projects/{project_id}/events'>>>[number]
