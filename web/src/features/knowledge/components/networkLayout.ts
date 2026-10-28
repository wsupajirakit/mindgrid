// Radial layout for the knowledge network: the project in the centre, its categories on an
// inner ring, each category's documents fanned out on an outer ring inside its own sector.
// Deterministic: the same graph always lands in the same place.
import type { GraphEdge, GraphNode } from '../api.ts'

export const WIDTH = 1000
export const HEIGHT = 640
const CX = WIDTH / 2
const CY = HEIGHT / 2
const R_CATEGORY = 150
const R_DOCUMENT = 255

export type Placed = GraphNode & { x: number, y: number, r: number }

function polar(radius: number, angle: number) {
  return { x: CX + radius * Math.cos(angle), y: CY + radius * Math.sin(angle) * 0.92 }
}

export function layout(nodes: GraphNode[]): Map<string, Placed> {
  const out = new Map<string, Placed>()
  const project = nodes.find((n) => n.kind === 'project')
  if (project) out.set(project.id, { ...project, x: CX, y: CY, r: 18 })
  const categories = nodes.filter((n) => n.kind === 'category')
  const step = (2 * Math.PI) / Math.max(categories.length, 1)
  categories.forEach((cat, i) => {
    const angle = -Math.PI / 2 + i * step
    out.set(cat.id, { ...cat, ...polar(R_CATEGORY, angle), r: 11 })
    const docs = nodes.filter((n) => n.kind === 'document' && n.category_id === cat.id)
    const spread = Math.min(step * 0.85, Math.PI * 0.9)
    docs.forEach((doc, j) => {
      const ring = R_DOCUMENT + (j % 3) * 34  // three staggered rows keep labels apart
      const t = docs.length === 1 ? 0 : j / (docs.length - 1) - 0.5
      const r = Math.min(4 + Math.sqrt(doc.chunks ?? 1) * 1.4, 14)
      out.set(doc.id, { ...doc, ...polar(ring, angle + t * spread), r })
    })
  })
  return out
}

export function neighbours(edges: GraphEdge[], id: string): Set<string> {
  const near = new Set([id])
  for (const e of edges) {
    if (e.source === id) near.add(e.target)
    if (e.target === id) near.add(e.source)
  }
  return near
}

/** A link drawn as a gentle curve bending toward the centre (or a straight spoke). */
export function linkPath(a: Placed, b: Placed, curved: boolean): string {
  if (!curved) return `M${a.x},${a.y} L${b.x},${b.y}`
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const qx = mx + (CX - mx) * 0.45
  const qy = my + (CY - my) * 0.45
  return `M${a.x},${a.y} Q${qx},${qy} ${b.x},${b.y}`
}

/** Faint background dust, fixed per seed. */
export function dust(count: number): { x: number, y: number, r: number, o: number }[] {
  let s = 1234567
  const rand = () => { s = (s * 16807) % 2147483647; return s / 2147483647 }
  return Array.from({ length: count }, () => ({
    x: rand() * WIDTH, y: rand() * HEIGHT, r: 0.6 + rand() * 1.8, o: 0.15 + rand() * 0.45,
  }))
}
