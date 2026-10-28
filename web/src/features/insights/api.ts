import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export type Summary = components['schemas']['SummaryOut']
export type Call = components['schemas']['CallOut']
export type QuestionDetail = components['schemas']['QuestionOut']

export const summaryQuery = (days: number, projectId: string | null) => queryOptions({
  queryKey: ['insights', 'summary', days, projectId],
  queryFn: ({ signal }) => api('get', 'insights/summary',
    { query: { days, project_id: projectId ?? undefined }, signal }),
})

export const callsQuery = (projectId: string | null, kind: 'run' | 'question' | null) =>
  queryOptions({
    queryKey: ['insights', 'calls', projectId, kind],
    queryFn: ({ signal }) => api('get', 'insights/calls', { query: {
      project_id: projectId ?? undefined, kind: kind ?? undefined, limit: 500 }, signal }),
  })

export const questionQuery = (id: string) => queryOptions({
  queryKey: ['insights', 'question', id],
  queryFn: ({ signal }) => api('get', 'insights/questions/{recall_id}',
    { path: { recall_id: id }, signal }),
})

