import { useQuery } from '@tanstack/react-query'
import { BookText, ChartNoAxesCombined, Database, FolderKanban, Workflow } from 'lucide-react'
import { useState } from 'react'
import { BarList, type BarRow, type Segment } from '../../../components/charts/BarList.tsx'
import { ChartCard } from '../../../components/charts/ChartCard.tsx'
import { Columns, type DayRow } from '../../../components/charts/Columns.tsx'
import { ALL, Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { PageHeader } from '../../../components/ui/PageHeader.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { StatCard } from '../../../components/ui/StatCard.tsx'
import { useDocumentTitle } from '../../../hooks/useBrand.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import { type Summary, summaryQuery } from '../api.ts'

type Row = Record<string, unknown>
const DAYS = [7, 30, 90, 365]
const num = (v: unknown) => (typeof v === 'number' ? v : 0)
const text = (v: unknown) => (typeof v === 'string' ? v : '')

const RUN_SEGMENTS = (): Segment[] => [
  { key: 'done', label: m.dash_done(), color: 'var(--status-good)' },
  { key: 'failed', label: m.dash_failed(), color: 'var(--status-critical)' },
  { key: 'other', label: m.dash_other(), color: 'var(--muted-foreground)' },
]
const COUNT = (label: string): Segment[] => [{ key: 'n', label, color: 'var(--series-1)' }]

/** Every day of the window, oldest first, zero where nothing happened. */
function daily(rows: Row[], days: number, keys: string[]): DayRow[] {
  const byDay = new Map(rows.map((r) => [text(r.day), r]))
  const out: DayRow[] = []
  const shown = Math.min(days, 90)
  for (let i = shown - 1; i >= 0; i--) {
    const day = new Date(Date.now() - i * 86_400_000).toISOString().slice(0, 10)
    const r = byDay.get(day)
    out.push({ day, values: Object.fromEntries(keys.map((k) => [k, num(r?.[k])])) })
  }
  return out
}

function tableOf(rows: BarRow[], segments: Segment[], first: string) {
  return {
    columns: [first, ...segments.map((s) => s.label)],
    rows: rows.map((r) => [r.sub ? `${r.label} · ${r.sub}` : r.label,
      ...segments.map((s) => r.values[s.key] ?? 0)]),
  }
}

function dayTable(rows: DayRow[], segments: Segment[]) {
  return {
    columns: [m.dash_day(), ...segments.map((s) => s.label)],
    rows: rows.filter((r) => segments.some((s) => r.values[s.key])).map((r) => [
      r.day, ...segments.map((s) => r.values[s.key] ?? 0)]),
  }
}

function Ranked({ title, description, rows, segments, first }: { title: string,
  description?: string, rows: BarRow[], segments: Segment[], first: string }) {
  return (
    <ChartCard title={title} description={description} empty={rows.length === 0}
      table={tableOf(rows, segments, first)}>
      <BarList rows={rows} segments={segments} />
    </ChartCard>
  )
}

function Charts({ data, days }: { data: Summary, days: number }) {
  const runs = daily(data.runs_daily, days, ['done', 'failed', 'other'])
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Ranked title={m.dash_by_playbook()} first={m.pb_playbook()} segments={RUN_SEGMENTS()}
        rows={data.runs_by_playbook.map((r) => ({ label: text(r.title), sub: text(r.playbook_id),
          values: { done: num(r.done), failed: num(r.failed), other: num(r.other) } }))} />
      <Ranked title={m.dash_docs_by_category()} first={m.docs_category()}
        segments={COUNT(m.dash_documents())}
        rows={data.documents_by_category.filter((r) => num(r.documents) > 0).map((r) => ({
          label: text(r.name), sub: text(r.project), values: { n: num(r.documents) } }))} />
      <Ranked title={m.dash_runs_by_project()} first={m.dash_projects()}
        segments={COUNT(m.dash_runs())}
        rows={data.runs_by_project.map((r) => ({ label: text(r.name),
          values: { n: num(r.total) } }))} />
      <ChartCard title={m.dash_runs_daily()} empty={data.runs_daily.length === 0}
        table={dayTable(runs, RUN_SEGMENTS())}>
        <Columns rows={runs} segments={RUN_SEGMENTS()} label={m.dash_runs_daily()} />
      </ChartCard>
      <Ranked title={m.dash_events_by_type()} first={m.dash_events_by_type()}
        segments={COUNT(m.dash_count())}
        rows={data.events_by_type.map((r) => ({ label: text(r.type),
          values: { n: num(r.total) } }))} />
    </div>
  )
}

/** `projects`: the ones to filter by (the page composes them from the projects list). */
export function DashboardPage({ projects }: { projects: { id: string, name: string }[] }) {
  useDocumentTitle(m.dash_title())
  const [days, setDays] = useState(30)
  const [project, setProject] = useState('')
  const summary = useQuery(summaryQuery(days, project || null))
  const t = summary.data?.totals ?? {}
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={<ChartNoAxesCombined />} title={m.dash_title()}
        description={m.dash_intro()} actions={(
          <div className="flex flex-wrap gap-2">
            <Select aria-label={m.dash_projects()} className="w-48" value={project || ALL}
              onChange={(v) => setProject(v === ALL ? '' : v)} options={[
                { value: ALL, label: m.dash_all_projects() },
                ...projects.map((p) => ({ value: p.id, label: p.name })),
              ]} />
            <Select aria-label={m.dash_day()} className="w-40" value={String(days)}
              onChange={(v) => setDays(Number(v))}
              options={DAYS.map((d) => ({ value: String(d),
                label: m.dash_days({ n: String(d) }) }))} />
          </div>
        )} />
      {summary.error ? <Notice tone="error">{errorText(summary.error)}</Notice> : null}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label={m.dash_projects()} value={t.projects ?? '—'} icon={<FolderKanban />} />
        <StatCard label={m.dash_documents()} value={t.documents ?? '—'} icon={<BookText />}
          hint={t.chunks === undefined ? undefined : m.dash_chunks({ n: String(t.chunks) })} />
        <StatCard label={m.dash_datasets()} value={t.datasets ?? '—'} icon={<Database />} />
        <StatCard label={m.dash_runs()} value={t.runs ?? '—'} icon={<Workflow />} />
      </div>
      {summary.data ? <Charts data={summary.data} days={days} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-72 rounded-xl" />)}
        </div>
      )}
    </div>
  )
}
