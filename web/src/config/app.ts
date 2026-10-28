// App-wide tunables: cache lifetimes and page sizes live here, never in components.
declare const __APP_API_BASE__: string

export const appConfig = {
  apiBase: __APP_API_BASE__,
  staleTime: { static: 5 * 60_000, list: 30_000 },
  auditPageSize: 50,
} as const
