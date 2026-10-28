// Typed client on native fetch: paths, parameters, bodies and responses all come from the
// generated OpenAPI types, so a backend change that breaks the web fails `tsc`.
import { appConfig } from '../../config/app.ts'
import { CSRF_HEADER, csrfToken } from './csrf.ts'
import { readError } from './error.ts'
import type { paths } from './openapi.gen.ts'

export { ApiError, shouldRetry } from './error.ts'

type Method = 'get' | 'post' | 'put' | 'patch' | 'delete'
type Strip<P> = P extends `/v1/${infer Rest}` ? Rest : never
/** API paths relative to the base that accept the method, e.g. 'projects/{project_id}'. */
export type PathOf<M extends Method> = Strip<{
  [P in keyof paths]: paths[P] extends { [K in M]: object } ? P : never
}[keyof paths]>
type Op<M extends Method, P extends PathOf<M>> = paths[`/v1/${P}`] extends { [K in M]: infer O }
  ? O : never
type Params<O> = O extends { parameters: infer R } ? R : never
type Body<O> = O extends { requestBody: { content: { 'application/json': infer B } } } ? B
  : O extends { requestBody?: { content: { 'application/json': infer B } } } ? B : never
type FormOf<O> = O extends { requestBody: { content: { 'multipart/form-data': unknown } } }
  ? FormData : never
type Success<O> = O extends { responses: infer R }
  ? R extends { 200: { content: { 'application/json': infer T } } } ? T
  : R extends { 201: { content: { 'application/json': infer T } } } ? T : void
  : never

export type Options<M extends Method, P extends PathOf<M>> = {
  path?: Params<Op<M, P>> extends { path: infer X } ? X : never
  query?: Params<Op<M, P>> extends { query?: infer X } ? X : never
  body?: Body<Op<M, P>>
  /** Multipart upload (the browser sets the content type and boundary). */
  form?: FormOf<Op<M, P>>
  signal?: AbortSignal
}

function url(template: string, path: object | undefined, query: object | undefined): string {
  const values = (path ?? {}) as Record<string, unknown>
  const filled = template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = values[key]
    if (value === undefined || value === null) throw new Error(`missing path param ${key}`)
    return encodeURIComponent(String(value))
  })
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) search.set(key, String(value))
  }
  const qs = search.toString()
  return `${appConfig.apiBase}${filled}${qs ? `?${qs}` : ''}`
}

/** A browser link to an API resource (for downloads opened in a new tab). */
export function apiHref(path: string): string {
  return `${appConfig.apiBase}${path}`
}

const listeners = new Set<() => void>()
/** Called on any 401: the session is gone (expired, revoked or signed out elsewhere). */
export function onSignedOut(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export async function api<M extends Method, P extends PathOf<M>>(
  method: M, path: P, options: Options<M, P> = {},
): Promise<Success<Op<M, P>>> {
  const hasBody = options.body !== undefined
  const res = await fetch(url(path, options.path as object, options.query as object), {
    method: method.toUpperCase(),
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      ...(method === 'get' ? {} : { [CSRF_HEADER]: csrfToken() }),
    },
    body: options.form ?? (hasBody ? JSON.stringify(options.body) : undefined),
    signal: options.signal,
  })
  if (res.status === 401) listeners.forEach((fn) => fn())
  if (!res.ok) throw await readError(res)
  if (res.status === 204) return undefined as Success<Op<M, P>>
  return (await res.json()) as Success<Op<M, P>>
}
