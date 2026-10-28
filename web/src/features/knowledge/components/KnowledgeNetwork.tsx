import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Checkbox } from '../../../components/ui/Field.tsx'
import { EmptyState } from '../../../components/ui/EmptyState.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { trustText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type GraphEdge, type GraphNode, graphQuery, type Trust } from '../api.ts'
import { dust, HEIGHT, layout, linkPath, neighbours, type Placed, WIDTH } from './networkLayout.ts'

const DUST = dust(140)

function edgeLabel(e: GraphEdge, target: Placed, docsIn: Map<string, number>): string {
  if (e.kind === 'together') return m.net_together({ n: String(e.weight ?? 1) })
  if (target.kind === 'category') return m.net_docs({ n: String(docsIn.get(target.id) ?? 0) })
  return target.trust ? trustText(target.trust as Trust) : ''
}

function Node({ n, dim, showName, onOpen }: { n: Placed, dim: boolean, showName: boolean,
  onOpen: (id: string) => void }) {
  const fill = n.kind === 'project' ? 'var(--net-project)'
    : n.kind === 'category' ? 'var(--net-category)' : 'var(--net-node)'
  const clickable = n.kind === 'document'
  return (
    <g opacity={dim ? 0.25 : 1} className={clickable ? 'cursor-pointer' : undefined}
      onClick={clickable ? () => onOpen(n.id) : undefined}>
      <title>{n.kind === 'document' ? `${n.label} · ${m.net_chunks({ n: String(n.chunks ?? 0) })}`
        : n.label}</title>
      <circle cx={n.x} cy={n.y} r={n.r * 2.2} fill={fill} opacity="0.18" className="net-pulse" />
      <circle cx={n.x} cy={n.y} r={n.r} fill="var(--net-bg-2)" stroke={fill} strokeWidth="2.5"
        filter="url(#net-glow)" />
      {n.kind === 'document' ? <circle cx={n.x} cy={n.y} r={n.r * 0.45} fill={fill} />
        : <circle cx={n.x} cy={n.y} r={n.r * 0.55} fill="none" stroke="var(--net-node-core)"
          strokeWidth="1.5" />}
      {showName ? (
        <text x={n.x} y={n.y + n.r + 13} textAnchor="middle" fill="var(--net-text)"
          fontSize={n.kind === 'document' ? 10 : 12} fontWeight={n.kind === 'document' ? 400 : 600}>
          {n.label.length > 24 ? `${n.label.slice(0, 23)}…` : n.label}
        </text>
      ) : null}
    </g>
  )
}


const LEGEND = (): [string, string, 'ring' | 'dot' | 'dash' | 'line'][] => [
  ['var(--net-project)', m.net_legend_project(), 'ring'],
  ['var(--net-category)', m.net_legend_category(), 'ring'],
  ['var(--net-node)', m.net_legend_document(), 'dot'],
  ['var(--net-link)', m.net_legend_contains(), 'dash'],
  ['var(--net-hot)', m.net_legend_together(), 'line'],
]

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
      {LEGEND().map(([color, label, shape]) => (
        <li key={label} className="inline-flex items-center gap-1.5">
          <svg viewBox="0 0 16 10" className="h-2.5 w-4" aria-hidden>
            {shape === 'ring'
              ? <circle cx="8" cy="5" r="4" fill="none" stroke={color} strokeWidth="2" />
              : shape === 'dot' ? <circle cx="8" cy="5" r="4" fill={color} />
                : <line x1="0" y1="5" x2="16" y2="5" stroke={color} strokeWidth="2"
                  strokeDasharray={shape === 'dash' ? '2 3' : undefined} />}
          </svg>
          {label}
        </li>
      ))}
    </ul>
  )
}

function Link({ e, a, b, dim, label }: { e: GraphEdge, a: Placed, b: Placed, dim: boolean,
  label: string | null }) {
  const together = e.kind === 'together'
  return (
    <g opacity={dim ? 0.12 : 1}>
      <path d={linkPath(a, b, together)} fill="none"
        stroke={together ? 'var(--net-hot)' : 'var(--net-link)'}
        strokeWidth={together ? Math.min(1 + (e.weight ?? 1) * 0.6, 4) : 1.4}
        strokeDasharray={together ? undefined : '2 6'} strokeLinecap="round"
        opacity={together ? 0.75 : 0.65} className={together ? undefined : 'net-flow'} />
      {label ? (
        <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} textAnchor="middle" fontSize="9"
          fill={together ? 'var(--net-hot)' : 'var(--net-text)'} opacity="0.85">{label}</text>
      ) : null}
    </g>
  )
}

/** The project's knowledge as a glowing network (the default view of the knowledge tab). */
export function KnowledgeNetwork({ projectId, onOpen }: { projectId: string,
  onOpen: (documentId: string) => void }) {
  const graph = useQuery(graphQuery(projectId))
  const [edgeLabels, setEdgeLabels] = useState(false)
  const [names, setNames] = useState(true)
  const [hover, setHover] = useState<string | null>(null)
  const nodes = useMemo(() => (graph.data?.nodes ?? []) as GraphNode[], [graph.data])
  const edges = useMemo(() => (graph.data?.edges ?? []) as GraphEdge[], [graph.data])
  const placed = useMemo(() => layout(nodes), [nodes])
  const docsIn = useMemo(() => {
    const counts = new Map<string, number>()
    for (const n of nodes) {
      if (n.category_id) counts.set(n.category_id, (counts.get(n.category_id) ?? 0) + 1)
    }
    return counts
  }, [nodes])
  const lit = hover ? neighbours(edges, hover) : null
  if (graph.error) return <Notice tone="error">{errorText(graph.error)}</Notice>
  if (!graph.data) return <Skeleton className="h-[480px] rounded-xl" />
  if (!nodes.some((n) => n.kind === 'document')) return <EmptyState text={m.net_empty()} />
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <Checkbox checked={edgeLabels} onChange={setEdgeLabels} label={m.net_edge_labels()} />
        <Checkbox checked={names} onChange={setNames} label={m.net_node_labels()} />
        <span className="text-xs text-muted-foreground">{m.net_hint()}</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-border">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-auto w-full" role="img"
          aria-label={m.net_title()} onMouseLeave={() => setHover(null)}>
          <defs>
            <radialGradient id="net-bg" cx="50%" cy="45%" r="75%">
              <stop offset="0" stopColor="var(--net-bg-1)" />
              <stop offset="1" stopColor="var(--net-bg-2)" />
            </radialGradient>
            <filter id="net-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          <rect width={WIDTH} height={HEIGHT} fill="url(#net-bg)" />
          {DUST.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r={d.r} fill="var(--net-dust)" opacity={d.o} />
          ))}
          {edges.map((e) => {
            const a = placed.get(e.source)
            const b = placed.get(e.target)
            if (!a || !b) return null
            return (
              <Link key={`${e.source}-${e.target}-${e.kind}`} e={e} a={a} b={b}
                dim={lit !== null && !(lit.has(e.source) && lit.has(e.target))}
                label={edgeLabels ? edgeLabel(e, b, docsIn) : null} />
            )
          })}
          {[...placed.values()].map((n) => (
            <g key={n.id} onMouseEnter={() => setHover(n.id)}>
              <Node n={n} dim={lit !== null && !lit.has(n.id)} showName={names} onOpen={onOpen} />
            </g>
          ))}
        </svg>
      </div>
      <Legend />
    </div>
  )
}
