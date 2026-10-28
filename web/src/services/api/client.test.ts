import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../testing/mocks/testServer.ts'
import { api, ApiError } from './client.ts'
import { errorText, KNOWN_ERROR_CODES } from './errorMessages.ts'

describe('api client', () => {
  it('sends the CSRF cookie value in a header on writes only', async () => {
    document.cookie = '__Host-mg_csrf=token-123; Secure; Path=/'
    const seen: (string | null)[] = []
    server.use(
      http.post('/v1/auth/sign-out', ({ request }) => {
        seen.push(request.headers.get('X-CSRF-Token'))
        return HttpResponse.json({ status: 'signed_out' })
      }),
      http.get('/v1/auth/me', ({ request }) => {
        seen.push(request.headers.get('X-CSRF-Token'))
        return HttpResponse.json({ id: 'u', email: 'e', display_name: 'd',
          system_role: 'user', locale: 'en' })
      }),
    )
    await api('post', 'auth/sign-out')
    await api('get', 'auth/me')
    expect(seen).toEqual(['token-123', null])
  })

  it('turns the error contract into an ApiError with a translated text', async () => {
    const failure = await api('post', 'auth/sign-in',
      { body: { email: 'a@b.c', password: 'nope' } }).catch((e: unknown) => e)
    expect(failure).toBeInstanceOf(ApiError)
    expect((failure as ApiError).code).toBe('auth.bad_credentials')
    expect(errorText(failure)).not.toBe('')
    expect(KNOWN_ERROR_CODES).toContain('auth.bad_credentials')
  })
})
