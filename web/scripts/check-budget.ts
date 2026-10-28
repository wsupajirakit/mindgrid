// Fails the build when the first-load JS or the CSS grows past the budget (gzip, level 9).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const LIMIT = { initialJs: 120 * 1024, css: 15 * 1024, lazyChunk: 60 * 1024 }
type Chunk = { file: string; isEntry?: boolean; imports?: string[]; css?: string[] }

const dist = 'dist'
const manifest = JSON.parse(
  readFileSync(join(dist, '.vite', 'manifest.json'), 'utf8'),
) as Record<string, Chunk>
const gz = (file: string) => gzipSync(readFileSync(join(dist, file)), { level: 9 }).length
const kb = (n: number) => `${(n / 1024).toFixed(1)} KB`

const initial = new Set<string>()
const visit = (key: string) => {
  const chunk = manifest[key]
  if (!chunk || initial.has(chunk.file)) return
  initial.add(chunk.file)
  chunk.imports?.forEach(visit)
}
Object.entries(manifest).filter(([, c]) => c.isEntry).forEach(([k]) => visit(k))

const jsFiles = new Set(Object.values(manifest).map((c) => c.file).filter((f) => f.endsWith('.js')))
const cssFiles = new Set(Object.values(manifest).flatMap((c) => c.css ?? []))
const initialJs = [...initial].filter((f) => f.endsWith('.js')).reduce((s, f) => s + gz(f), 0)
const css = [...cssFiles].reduce((s, f) => s + gz(f), 0)

const failures: string[] = []
for (const file of jsFiles) {
  const size = gz(file)
  const tag = initial.has(file) ? 'initial' : 'lazy'
  console.log(`${tag.padEnd(8)} ${kb(size).padStart(9)}  ${file}`)
  if (tag === 'lazy' && size > LIMIT.lazyChunk) failures.push(`${file} ${kb(size)} > 60 KB`)
}
console.log(`initial JS gzip ${kb(initialJs)} (limit ${kb(LIMIT.initialJs)})`)
console.log(`CSS gzip        ${kb(css)} (limit ${kb(LIMIT.css)})`)
if (initialJs > LIMIT.initialJs) failures.push(`initial JS ${kb(initialJs)} > 120 KB`)
if (css > LIMIT.css) failures.push(`CSS ${kb(css)} > 15 KB`)
if (failures.length > 0) {
  console.error(`check-budget FAILED:\n  ${failures.join('\n  ')}`)
  process.exit(1)
}
console.log('check-budget OK')
