// MSW handlers shared by tests (and dev:mock): the same error contract as the server.
import { http, HttpResponse } from 'msw'

export const base = '/v1'
export const ME = { id: 'u1', email: 'alice@example.com', display_name: 'Alice',
  system_role: 'superadmin', locale: 'en', avatar: '' }

export const PACK = {
  version: 'context-pack/1', query: '', project_id: 'p1', created_at: '2026-10-25T00:00:00Z',
  rules: 'Answer only from the passages.', rendered: '', space: '', reranker: '', dropped: 2,
  skipped: { vector: 'nothing indexed in this embedding space yet' },
  passages: [{ ref: 'P1', chunk_id: 'k1', document_id: 'd1', title: 'macro.md',
    heading: 'Rates', trust: 'claimed', location: {}, text: 'Treasury yields rose.',
    relevance: 0.91 }],
}

const SUBS: Record<string, unknown>[] = []
const NOW = '2026-10-25T00:00:00Z'

const USERS = [
  { id: 'u1', email: 'alice@example.com', display_name: 'Alice', system_role: 'superadmin',
    status: 'active', avatar: 'aurora', last_login_at: NOW, created_at: NOW },
  ...Array.from({ length: 11 }, (_, i) => ({ id: `u${String(i + 2)}`,
    email: `user${String(i + 2)}@example.com`, display_name: `User ${String(i + 2)}`,
    system_role: 'user', status: 'active', avatar: '', last_login_at: null, created_at: NOW })),
]

/** Every write the tests make, as [method, path under the API base, body]. */
export const writes: [string, string, unknown][] = []

/** Start a test with a saved account preference (as if chosen earlier). */
export function savePreference(key: string, value: string) {
  prefs[key] = value
}

/** Forget what the previous test wrote. */
export function resetMockState() {
  writes.length = 0
  prefs = { ...DEFAULT_PREFS }
}
const apiPath = (request: Request) => new URL(request.url).pathname.slice(base.length + 1)
const record = async (request: Request) => {
  const body: unknown = request.headers.get('content-type')?.includes('json')
    ? await request.json() : null
  writes.push([request.method, apiPath(request), body])
}

const PLAYBOOK = { id: 'core.table-screen', title: 'Screen a table',
  summary: 'Filter, rank and keep the top rows.', enabled: true, pinned_version: null,
  params: {}, inputs: ['rows'], param_names: ['top_n'], functions: ['filter', 'rank', 'top'],
  translations: { th: { title: 'คัดกรองตาราง', summary: 'เก็บ จัดอันดับ คืนแถวต้น ๆ' } },
  versions: [{ version: 1, status: 'active' }, { version: 2, status: 'paused' }] }
const DEFAULT_PREFS: Record<string, string> = { 'ui.locale': 'en', 'ui.theme': 'dark',
  'ui.layout': 'sidebar' }
let prefs = { ...DEFAULT_PREFS }  // what PUT me/settings stored, like the server would
const PROJECTS = [{ id: 'p1', owner_id: 'u1', slug: 'alpha', name: 'Alpha', description: '',
  archived: false }, { id: 'p2', owner_id: 'u1', slug: 'beta', name: 'Beta', description: '',
  archived: false }]
const KEYS = [{ id: 'k1', key_id: 'mgk_old', owner_user_id: 'u1', name: 'ci', scopes: ['read'],
  project_ids: [], expires_at: NOW, revoked_at: null, last_used_at: null }]

export const handlers = [
  http.get(`${base}/meta/brand`, () => HttpResponse.json({ name: 'Test Brand',
    short_name: 'Test', tagline: '', logo_url: '', primary_color: '#336699',
    primary_color_dark: '#6699cc' })),
  http.post(`${base}/auth/sign-in`, async ({ request }) => {
    const body = (await request.json()) as { password: string }
    if (body.password !== 'correct horse battery staple') {
      return HttpResponse.json({ error: { code: 'auth.bad_credentials', message: 'wrong',
        params: {} } }, { status: 401 })
    }
    return HttpResponse.json(ME)
  }),
  http.get(`${base}/auth/me`, () => HttpResponse.json(ME)),
  http.get(`${base}/projects/:id/categories`, () => HttpResponse.json([
    { id: 'c1', project_id: 'p1', slug: 'macro', name: 'Macro', description: '',
      restricted: true, my_level: 'manage' }])),
  http.get(`${base}/playbooks`, ({ request }) => {
    // Project "p-none" has nothing assigned; elsewhere the playbook is on.
    const project = new URL(request.url).searchParams.get('project_id')
    return HttpResponse.json([{ ...PLAYBOOK, enabled: project !== 'p-none' }])
  }),
  http.get(`${base}/playbooks/:id/assignments`, () => HttpResponse.json({
    playbook_id: PLAYBOOK.id, all_projects: true, projects: [
      { project_id: 'p1', name: 'Alpha', enabled: true, own_choice: false, can_manage: true },
      { project_id: 'p2', name: 'Beta', enabled: true, own_choice: false, can_manage: true }] })),
  http.put(`${base}/playbooks/:id/assignments`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ playbook_id: PLAYBOOK.id, all_projects: false, projects: [] })
  }),
  http.put(`${base}/admin/playbooks/:id/translations/:locale`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.put(`${base}/admin/playbooks/:id/override`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${base}/audit`, () => HttpResponse.json([{ id: 'a1', at: NOW,
    actor_user_id: 'u1', actor_superadmin: false, project_id: 'p1', action: 'member.set',
    target_type: 'user', target_id: 'u2', details: { role: 'viewer' }, request_id: 'r1',
    actor: { name: 'Alice', email: 'alice@example.com', avatar: '' },
    people: { u2: { name: 'Bob', email: 'bob@example.com', avatar: '' } } }])),
  http.get(`${base}/groups`, () => HttpResponse.json([
    { id: 'g1', name: 'Analysts', description: 'Research team', members: 2 }])),
  http.post(`${base}/admin/groups`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ id: 'g2', name: 'Ops', description: '', members: 0 },
      { status: 201 })
  }),
  http.get(`${base}/admin/groups/:id/members`, () => HttpResponse.json([
    { user_id: 'u2', name: 'User 2', email: 'user2@example.com', avatar: '' }])),
  http.put(`${base}/admin/groups/:id/members/:user`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${base}/projects/:id/groups`, () => HttpResponse.json([])),
  http.put(`${base}/projects/:id/groups/:group`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${base}/projects/:id/people`, () => HttpResponse.json([
    { user_id: 'u1', name: 'Alice', email: 'alice@example.com', avatar: '', role: null,
      own_role: null, via: [], owner: true },
    { user_id: 'u2', name: 'Bob', email: 'bob@example.com', avatar: '', role: 'viewer',
      own_role: null, via: [{ group_id: 'g1', name: 'Analysts', role: 'viewer' }],
      owner: false }])),
  http.put(`${base}/projects/:id/members/:user`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ user_id: 'u2', role: 'editor' })
  }),
  http.get(`${base}/categories/:id/access`, () => HttpResponse.json({ restricted: true,
    groups: [], people: [
      { user_id: 'u2', name: 'Bob', email: 'bob@example.com', avatar: '', role: 'viewer',
        granted: 'none', via_groups: 'none', level: 'none', fixed: false }] })),
  http.put(`${base}/categories/:id/group-grants/:group`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.put(`${base}/categories/:id/grants/:user`, async ({ request }) => {
    await record(request)
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(`${base}/admin/projects/:id/copy`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ categories: 1, documents: 3, playbooks: 1 })
  }),
  http.get(`${base}/me/settings`, () => HttpResponse.json(Object.entries(prefs).map(
    ([key, value]) => ({ key, value, source: 'user', doc: '', schema: {} })))),
  http.put(`${base}/me/settings/:key`, async ({ request, params }) => {
    await record(request)
    prefs[String(params.key)] = String((writes.at(-1)?.[2] as { value: string }).value)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${base}/projects`, () => HttpResponse.json(PROJECTS)),
  http.get(`${base}/admin/api-keys`, () => HttpResponse.json(KEYS)),
  http.post(`${base}/admin/api-keys/:id/rotate`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ key: { ...KEYS[0], id: 'k2', key_id: 'mgk_new' },
      private_key_pem: '-----BEGIN PRIVATE KEY-----NEW' }, { status: 201 })
  }),
  http.put(`${base}/projects/:id/playbooks/:pid`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({})
  }),
  http.get(`${base}/admin/users`, () => HttpResponse.json(USERS)),
  http.post(`${base}/admin/users`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({ ...USERS[1], id: 'u99' }, { status: 201 })
  }),
  http.patch(`${base}/admin/users/:id`, async ({ request }) => {
    await record(request)
    return HttpResponse.json(USERS[1])
  }),
  http.get(`${base}/projects/:id/connectors`, () => HttpResponse.json([])),
  http.get(`${base}/connector-templates`, () => HttpResponse.json([{ id: 'zservice',
    title: 'z-service', summary: '', spec: { url: 'https://z.test/x' }, every_minutes: 60 }])),
  http.put(`${base}/projects/:id/connectors/:name`, async ({ request }) => {
    await record(request)
    return HttpResponse.json({})
  }),
  http.get(`${base}/projects/:id/datasets`, () => HttpResponse.json([])),
  http.post(`${base}/projects/:id/datasets/:name`, async ({ request }) => {
    writes.push([request.method, apiPath(request), null])
    return HttpResponse.json({ name: 'prices', version: 1, created: true }, { status: 201 })
  }),
  http.get(`${base}/playbooks/:id/versions/:v`, () => HttpResponse.json({
    id: 'core.table-screen', version: 1, status: 'active', title: 'Screen a table',
    summary: 'Keep, rank, top.', inputs: { rows: { type: 'array', doc: 'The table' } },
    params: { top_n: { type: 'integer', default: 10, doc: 'Rows returned' } } })),
  http.get(`${base}/projects/:id/evals`, () => HttpResponse.json([{ id: 'ev1', name: 'basics',
    k: 3, created_at: '2026-10-25T00:00:00Z', setup: { reranker: 'local:rr', space: 's' },
    metrics: { hit_at_k: 1, recall_at_k: 1, mrr: 0.75, ndcg_at_k: 0.8, abstention: 1, cases: 2 },
    cases: [{ query: 'stops?', expect: ['#stops'], found: ['p#Stops'], hit: 1, abstained: null },
      { query: 'cake?', expect: [], found: [], hit: 1, abstained: true }],
    judging: null, judgements: [{ id: 'j1', judge: 'local:judge', answerer: '',
      created_at: '2026-10-25T00:01:00Z', cases: [],
      metrics: { judged: 1, failed: 0, judge_context: 0.5, judge_faithfulness: 0,
        answered: 0 } }] }])),
  http.get(`${base}/events/types`, () => HttpResponse.json([
    { type: 'run.completed', summary: '', data: {} }])),
  http.get(`${base}/projects/:id/event-subscriptions`, () => HttpResponse.json(SUBS)),
  http.get(`${base}/projects/:id/events`, () => HttpResponse.json([{ id: 'e1',
    type: 'run.completed', subject: 'runs/r1', created_at: '2026-10-25T00:00:00Z',
    data: { links: { ui: '/projects/p1?tab=runs&run=r1', api: '' } } }])),
  http.post(`${base}/projects/:id/event-subscriptions`, async ({ request }) => {
    const body = (await request.json()) as { name: string, url: string, event_types: string[] }
    const sub = { id: 's2', project_id: 'p1', enabled: true, dead_in_a_row: 0,
      disabled_reason: '', created_at: '2026-10-25T00:00:00Z', ...body }
    SUBS.push(sub)
    return HttpResponse.json({ subscription: sub, secret: 'whsec_TEST' }, { status: 201 })
  }),
  http.post(`${base}/projects/:id/context-pack`, async ({ request }) => {
    const body = (await request.json()) as { query: string }
    return HttpResponse.json({ ...PACK, query: body.query })
  }),
]
