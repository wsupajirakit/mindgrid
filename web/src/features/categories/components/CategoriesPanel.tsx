import { useQuery } from '@tanstack/react-query'
import { Lock, Pencil, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge.tsx'
import { Button } from '../../../components/ui/Button.tsx'
import { type Column, DataTable } from '../../../components/ui/DataTable.tsx'
import { levelText } from '../../../i18n/enums.ts'
import { m } from '../../../paraglide/messages.js'
import { categoriesQuery, type Category } from '../api.ts'
import { AccessDialog, type GroupChoice } from './AccessDialog.tsx'
import { EditCategoryDialog } from './EditCategoryDialog.tsx'
import { NewCategoryButton } from './NewCategoryDialog.tsx'

type Open = { kind: 'access' | 'edit', category: Category } | null

/** A project's categories: create, edit, and decide who can do what in each (people and
 * groups); `groups` are the ones that may be given access (composed by the page). */
export function CategoriesPanel({ projectId, groups }: { projectId: string,
  groups: GroupChoice[] }) {
  const categories = useQuery(categoriesQuery(projectId))
  const [open, setOpen] = useState<Open>(null)
  const columns: Column<Category>[] = [
    { accessorKey: 'name', header: () => m.col_name(), cell: ({ row }) => (
      <span className="flex min-w-0 flex-col">
        <span className="font-medium">{row.original.name}</span>
        {row.original.description ? (
          <span className="line-clamp-1 text-xs text-muted-foreground">
            {row.original.description}
          </span>
        ) : null}
      </span>
    ) },
    { accessorKey: 'slug', header: () => m.col_slug(),
      cell: ({ row }) => <code className="text-xs">{row.original.slug}</code> },
    { accessorKey: 'restricted', header: () => m.col_access(), cell: ({ row }) =>
      row.original.restricted ? (
        <Badge tone="warning"><Lock className="size-3" />{m.category_restricted()}</Badge>
      ) : <Badge tone="outline">{m.cat_open()}</Badge> },
    { accessorKey: 'my_level', header: () => m.col_my_level(),
      cell: ({ row }) => <Badge tone="outline">{levelText(row.original.my_level)}</Badge> },
    { id: 'actions', header: () => m.ui_actions(), enableSorting: false, cell: ({ row }) =>
      row.original.my_level === 'manage' ? (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="sm"
            onClick={() => setOpen({ kind: 'access', category: row.original })}>
            <ShieldCheck />{m.cat_access()}
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label={m.ui_edit()}
            onClick={() => setOpen({ kind: 'edit', category: row.original })}><Pencil /></Button>
        </span>
      ) : null },
  ]
  return (
    <>
      <DataTable data={categories.data ?? []} columns={columns} empty={m.categories_empty()}
        loading={categories.isPending} toolbar={<NewCategoryButton projectId={projectId} />} />
      {open?.kind === 'access' ? <AccessDialog category={open.category} groups={groups}
        onClose={() => setOpen(null)} /> : null}
      {open?.kind === 'edit' ? <EditCategoryDialog category={open.category}
        onClose={() => setOpen(null)} /> : null}
    </>
  )
}
