import { queryOptions } from '@tanstack/react-query'
import { api } from '../../services/api/client.ts'
import type { components } from '../../services/api/openapi.gen.ts'

export const meQuery = queryOptions({
  queryKey: ['auth', 'me'],
  queryFn: ({ signal }) => api('get', 'auth/me', { signal }),
  retry: false,
})

export type Me = components['schemas']['Me']

export function signIn(email: string, password: string) {
  return api('post', 'auth/sign-in', { body: { email, password } })
}

export function signOut() {
  return api('post', 'auth/sign-out')
}

export function updateProfile(profile: { display_name?: string, avatar?: string }) {
  return api('patch', 'auth/me', { body: profile })
}

export function changePassword(current: string, next: string) {
  return api('post', 'auth/password', { body: { current_password: current, new_password: next } })
}
