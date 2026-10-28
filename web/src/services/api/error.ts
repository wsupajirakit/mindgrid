// The error contract of the API: {"error": {"code", "message", "params"}}.
export type ErrorParams = Record<string, string | number | boolean | string[]>

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly params: ErrorParams

  constructor(status: number, code: string, message: string, params: ErrorParams = {}) {
    super(message)
    this.status = status
    this.code = code
    this.params = params
  }
}

/** Retry only what a retry can fix: network failures and server overload. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false
  return !(error instanceof ApiError) || error.status >= 500 || error.status === 429
}

export async function readError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: unknown, message?: unknown,
      params?: unknown } }
    const err = body.error ?? {}
    const code = typeof err.code === 'string' ? err.code : `http.status_${res.status}`
    const message = typeof err.message === 'string' ? err.message : res.statusText
    const params = (err.params && typeof err.params === 'object' ? err.params : {}) as ErrorParams
    return new ApiError(res.status, code, message, params)
  } catch {
    return new ApiError(res.status, `http.status_${res.status}`, res.statusText)
  }
}
