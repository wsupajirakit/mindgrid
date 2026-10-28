# Web UI conventions

The rules every page follows. The lint config enforces some of them (layers, colours,
text); the rest are kept by review against this page.

## Shell

`layouts/AppShell.tsx` frames every signed-in page, using the pieces in `layouts/shell/`.
Pages use the full width.

- **Layout:** each account picks one in the account menu.
  - *Sidebar:* Workspace links, plus Admin links for superadmins. It collapses to icons
    (kept in `localStorage`).
  - *Mega menu:* a top bar with an *Explore* panel. Sections sit on the left; the chosen
    section's destinations fill a two-column grid; a call to action sits below.
  - On small screens both become a drawer.
- **Header:** the language toggle (EN/TH), the theme toggle (sun/moon, asks first) and the
  account menu (profile and avatar, password, settings, menu layout, sign out with a
  confirm).
- **Hosts:** the toast, confirmation and tooltip hosts are mounted once, here.

**Preferences:**
- Language, theme and layout are stored per user (`ui.locale`, `ui.theme`, `ui.layout` in
  `me/settings`) and applied on sign-in. With nothing stored, the defaults are English,
  dark and sidebar.
- A change is shown at once and then saved (`layouts/shell/preferences.ts`).
- Switching the language re-renders every page through `app/LocaleRoot.tsx`, with no reload.
- `public/theme-init.js` paints the last theme before the scripts load.

**Colours:** the brand config supplies `--brand` (light theme) and `--brand-dark` (dark
theme), so the primary colour is configured in one place.

## Building blocks (`components/ui`)

| Need | Use |
|---|---|
| A page title, its purpose and main actions | `PageHeader` |
| A surface with a header and actions | `Card` |
| A card with a generated picture | `CoverCard` (`Cover` draws from a seed; no image files) |
| A list of records | `DataTable`: search, sorting, 10/20/50/100 per page |
| A card grid that can be searched | `SearchBox` + `matches()` |
| Cards per row (2/4/6/8, shared, kept locally) | `CardsPerRowToggle` + `cardGridClass()` in a `@container` |
| Pick one value | `Select` (themed Radix; `ALL` for an "all"/"none" choice, `placeholder` for none yet) |
| Create or edit anything | `FormModal` (Enter submits; the button shows progress) |
| Show details | `Modal`, with `DetailSection` / `JsonBlock` |
| Delete, switch on/off, anything hard to undo | `await confirm({...})`, never `window.confirm` |
| Report the outcome of a change | `useAction().run(work, successText)`: a toast either way |
| Nothing to show | `EmptyState`; while loading, `Skeleton` |
| A person | `Avatar` (preset or initials) |

A form control's accessible name is its `Field` label alone; hints and errors sit outside
the label.

## Layers

- **Features never import other features.** When a page needs two of them, the page
  composes them and passes data or a render prop. For example, `pages/_app/results.tsx`
  hands the playbooks feature's `RunById` to the insights results page.
- **Shared folders** (`components`, `hooks`, `services`, `utils`, `testing`) never import
  features.
- **API paths** live in `services/api` and each feature's `api.ts`.

## Text and colour

- **Text:** every visible string is a Paraglide message in `messages/{en,th,it}.json`.
  `npm run check-i18n` fails if a locale is missing a key.
- **Colour:** colours come from the CSS variables in `styles/index.css`. There are no hex or
  rgb literals in components.
- **Charts:** charts use the validated `--series-1..6` palette and the reserved
  `--status-good` / `--status-critical`. Every chart card offers a table view, and values
  are labelled directly.

## Tests

`testing/render.tsx` (`renderApp`) mounts a component with the same hosts as the shell, so
a test can follow a change from its modal, through its confirm, to its toast.
`testing/mocks/handlers.ts` answers the API and records every write in `writes`, so a test
can check what was sent.
