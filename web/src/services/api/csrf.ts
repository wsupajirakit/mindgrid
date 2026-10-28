// The CSRF cookie set at sign-in; echoed in a header on every state-changing request.
const CSRF_COOKIE = '__Host-mg_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

export function csrfToken(): string {
  const prefix = `${CSRF_COOKIE}=`
  const found = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return found ? decodeURIComponent(found.slice(prefix.length)) : ''
}
