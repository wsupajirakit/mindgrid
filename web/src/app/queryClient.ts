import { QueryClient } from '@tanstack/react-query'
import { shouldRetry } from '../services/api/client.ts'

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: shouldRetry, refetchOnWindowFocus: false } },
  })
}
