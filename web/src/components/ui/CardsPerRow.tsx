// The cards-per-row picker of a card grid, and the grid classes for each choice. The choice
// is the most a row holds: a narrower grid (its own width, not the window's) holds fewer.
import { Columns2, Grid2x2, Grid3x3, LayoutGrid } from 'lucide-react'
import { m } from '../../paraglide/messages.js'
import {
  CARDS_PER_ROW, type CardsPerRow, setCardsPerRow, useCardsPerRow,
} from '../../stores/cardsPerRow.ts'
import { ViewToggle } from './ViewToggle.tsx'

const ICONS = { 2: <Columns2 />, 4: <Grid2x2 />, 6: <Grid3x3 />, 8: <LayoutGrid /> }

// Full class strings so Tailwind sees them; widths are container queries on the grid.
const GRID: Record<CardsPerRow, string> = {
  2: 'grid-cols-1 gap-4 @lg:grid-cols-2',
  4: 'grid-cols-1 gap-4 @md:grid-cols-2 @3xl:grid-cols-4',
  6: 'grid-cols-1 gap-3 @sm:grid-cols-2 @xl:grid-cols-3 @3xl:grid-cols-6',
  8: 'grid-cols-2 gap-3 @xl:grid-cols-4 @4xl:grid-cols-8',
}

/** Wrap the grid in an element with `@container` (see `CardGrid`). */
export const cardGridClass = (n: CardsPerRow) => `grid ${GRID[n]}`

/** True when cards are small enough to need their compact layout. */
export const isCompact = (n: CardsPerRow) => n >= 6

export function CardsPerRowToggle() {
  const value = useCardsPerRow()
  return (
    <ViewToggle size="md" label={m.ui_cards_per_row()} value={String(value)}
      onChange={(v) => setCardsPerRow(Number(v) as CardsPerRow)}
      options={CARDS_PER_ROW.map((n) => ({ value: String(n), icon: ICONS[n], label: String(n),
        hint: m.ui_cards_per_row_n({ n: String(n) }) }))} />
  )
}
