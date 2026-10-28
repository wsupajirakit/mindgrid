import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'

export const evalsQuery = (projectId: string) => queryOptions({
  queryKey: ['projects', projectId, 'evals'],
  queryFn: ({ signal }) => api('get', 'projects/{project_id}/evals',
    { path: { project_id: projectId }, signal }),
})

export function runEval(projectId: string, golden: unknown) {
  return api('post', 'projects/{project_id}/evals',
    { path: { project_id: projectId }, body: golden as never })
}

export type EvalRun = Awaited<ReturnType<typeof runEval>>

export const EXAMPLE = JSON.stringify({
  name: 'basics', k: 5,
  cases: [
    { query: 'a question the knowledge answers', expect: ['document title#section'] },
    { query: 'an off-topic question', expect: [] },
  ],
}, null, 2)
