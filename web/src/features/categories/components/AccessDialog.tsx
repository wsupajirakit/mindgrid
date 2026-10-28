import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, Plus, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { DetailSection } from '../../../components/ui/Detail.tsx'
import { Modal } from '../../../components/ui/Dialog.tsx'
import { Select } from '../../../components/ui/Select.tsx'
import { Notice } from '../../../components/ui/Notice.tsx'
import { Person } from '../../../components/ui/Person.tsx'
import { Skeleton } from '../../../components/ui/Skeleton.tsx'
import { useAction } from '../../../hooks/useAction.ts'
import { levelText, roleText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { errorText } from '../../../services/api/errorMessages.ts'
import {
  accessQuery, type Category, type CategoryAccess, type LevelName, LEVELS, setGroupGrant,
  setPersonGrant,
} from '../api.ts'

type PersonRow = CategoryAccess['people'][number]
export type GroupChoice = { id: string, name: string }

function LevelSelect({ value, label, onChange, none }: { value: string, label: string,
  onChange: (level: LevelName) => void, none: string }) {
  return (
    <Select aria-label={label} className="h-8 w-36" value={value}
      onChange={(v) => onChange(v as LevelName)}
      options={LEVELS.map((l) => ({ value: l, label: l === 'none' ? none : levelText(l) }))} />
  )
}

function Groups({ category, data, groups, save }: { category: Category, data: CategoryAccess,
  groups: GroupChoice[], save: (work: () => Promise<unknown>) => Promise<void> }) {
  const [adding, setAdding] = useState('')
  const listed = new Set(data.groups.map((g) => g.group_id))
  return (
    <DetailSection title={m.nav_groups()}>
      {data.groups.length === 0 ? <p className="text-sm text-muted-foreground">
        {m.cat_no_group_grants()}</p> : null}
      <ul className="flex flex-col gap-2">
        {data.groups.map((g) => (
          <li key={g.group_id} className="flex items-center gap-3 rounded-lg border
            border-border px-3 py-2 text-sm">
            <UsersRound className="size-4 text-primary" />
            <span className="flex-1 font-medium">{g.name}</span>
            <LevelSelect value={g.level} label={g.name} none={m.cat_grant_remove()}
              onChange={(l) => void save(() => setGroupGrant(category.id, g.group_id, l))} />
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Select aria-label={m.cat_add_group()} value={adding} onChange={setAdding}
          placeholder={m.cat_add_group()} options={groups.filter((g) => !listed.has(g.id))
            .map((g) => ({ value: g.id, label: g.name }))} />
        <Button variant="outline" disabled={!adding} onClick={() => void save(async () => {
          await setGroupGrant(category.id, adding, 'read')
          setAdding('')
        })}><Plus />{m.action_add()}</Button>
      </div>
    </DetailSection>
  )
}

function peopleColumns(category: Category, save: (w: () => Promise<unknown>) => Promise<void>) {
  const columns: Column<PersonRow>[] = [
    { id: 'person', accessorFn: (p) => `${p.name} ${p.email}`, header: () => m.col_user(),
      cell: ({ row }) => <Person person={row.original} fallback="" /> },
    { accessorKey: 'role', header: () => m.col_role(), cell: ({ row }) =>
      row.original.role === 'owner' ? <Badge tone="primary">{m.mem_owner()}</Badge>
        : <Badge>{row.original.role ? roleText(row.original.role) : '—'}</Badge> },
    { accessorKey: 'via_groups', header: () => m.cat_via_groups(), cell: ({ row }) =>
      row.original.via_groups === 'none' ? '—' : levelText(row.original.via_groups) },
    { accessorKey: 'granted', header: () => m.cat_own_grant(), cell: ({ row }) =>
      row.original.fixed ? <span className="text-xs text-muted-foreground">
        {m.cat_always_manage()}</span> : (
        <LevelSelect value={row.original.granted} label={row.original.name}
          none={m.cat_grant_none()}
          onChange={(l) => void save(() => setPersonGrant(category.id, row.original.user_id, l))} />
      ) },
    { accessorKey: 'level', header: () => m.cat_level_now(), cell: ({ row }) => (
      <Badge tone={row.original.level === 'none' ? 'destructive' : 'success'}>
        {levelText(row.original.level)}
      </Badge>
    ) },
  ]
  return columns
}

/** Who can do what in a category: grants per group (every member) and per person (wins). */
export function AccessDialog({ category, groups, onClose }: { category: Category,
  groups: GroupChoice[], onClose: () => void }) {
  const access = useQuery(accessQuery(category.id))
  const queryClient = useQueryClient()
  const { run } = useAction()
  const save = async (work: () => Promise<unknown>) => {
    await run(async () => {
      await work()
      await queryClient.invalidateQueries({ queryKey: accessQuery(category.id).queryKey })
    }, m.cat_access_saved())
  }
  return (
    <Modal open onOpenChange={(o) => { if (!o) onClose() }} size="xl"
      title={m.cat_access_title({ name: category.name })}>
      <div className="flex flex-col gap-5">
        <Notice tone={category.restricted ? 'warn' : 'info'}>
          {category.restricted ? m.cat_access_restricted() : m.cat_access_open()}
        </Notice>
        {access.error ? <Notice tone="error">{errorText(access.error)}</Notice> : null}
        {access.data ? (
          <>
            <Groups category={category} data={access.data} groups={groups} save={save} />
            <DetailSection title={m.mem_people_title()}>
              <DataTable data={access.data.people} columns={peopleColumns(category, save)}
                empty={m.members_empty()} />
            </DetailSection>
          </>
        ) : <Skeleton className="h-40" />}
        {category.restricted ? null : (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="size-3.5" />{m.cat_access_tip()}
          </p>
        )}
      </div>
    </Modal>
  )
}
