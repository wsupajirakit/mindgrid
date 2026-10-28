// Fails when a message key is missing in any locale, is empty, or its placeholders differ
// between locales. A message is a string, or (plural and other variants) the inlang
// message-format array [{ declarations, selectors, match: { "<selector>=<case>": "text" } }].
import { readFileSync } from 'node:fs'

const settings = JSON.parse(readFileSync('project.inlang/settings.json', 'utf8')) as {
  locales: string[]
}
type Variant = { declarations?: string[], selectors?: string[], match?: Record<string, string> }
type Messages = Record<string, unknown>
const load = (l: string) => JSON.parse(readFileSync(`messages/${l}.json`, 'utf8')) as Messages
const byLocale = new Map(settings.locales.map((l) => [l, load(l)]))
const keysOf = (m: Messages) => Object.keys(m).filter((k) => k !== '$schema')

/** Every text a message can show: the string itself, or each variant's texts. */
function texts(value: unknown): string[] | null {
  if (typeof value === 'string') return value === '' ? null : [value]
  if (!Array.isArray(value) || value.length === 0) return null
  const all = (value as Variant[]).flatMap((v) => Object.values(v.match ?? {}))
  return all.length > 0 && all.every((t) => typeof t === 'string' && t !== '') ? all : null
}

/** Placeholders the message can use (union over variants), plus declared inputs. */
function placeholders(value: unknown, shown: string[]): string {
  const names = new Set(shown.flatMap((t) => [...t.matchAll(/\{(\w+)\}/g)].map((x) => x[1])))
  if (Array.isArray(value)) {
    for (const v of value as Variant[]) {
      for (const d of v.declarations ?? []) {
        const input = /^input (\w+)$/.exec(d)
        if (input?.[1]) names.add(input[1])
      }
    }
  }
  return [...names].sort().join(',')
}

const allKeys = new Set([...byLocale.values()].flatMap(keysOf))
const errors: string[] = []
for (const key of allKeys) {
  const seen = new Map<string, string>()
  for (const [locale, msgs] of byLocale) {
    if (!(key in msgs)) {
      errors.push(`missing "${key}" in ${locale}`)
      continue
    }
    const shown = texts(msgs[key])
    if (!shown) errors.push(`empty or malformed "${key}" in ${locale}`)
    else seen.set(locale, placeholders(msgs[key], shown))
  }
  if (new Set(seen.values()).size > 1) {
    errors.push(`placeholders differ for "${key}": ${JSON.stringify(Object.fromEntries(seen))}`)
  }
}
if (errors.length > 0) {
  console.error(`check-i18n FAILED:\n  ${errors.join('\n  ')}`)
  process.exit(1)
}
console.log(`check-i18n OK: ${allKeys.size} keys x ${byLocale.size} locales`)
