import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { changeLocale } from '../i18n/locale.ts'
import { setNavLayout } from '../stores/layout.ts'
import { savePreference, writes } from '../testing/mocks/handlers.ts'
import { renderApp } from '../testing/render.tsx'
import { AppShell } from './AppShell.tsx'

afterEach(() => { changeLocale('en'); setNavLayout('sidebar') })

const shell = () => renderApp(<AppShell><p>{'page-body'}</p></AppShell>)

describe('app shell', () => {
  it('switches to the mega menu from the account menu and saves the choice', async () => {
    shell()
    expect(await screen.findByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    fireEvent.pointerDown(await screen.findByRole('button', { name: /account/i }),
      { button: 0, pointerType: 'mouse' })
    fireEvent.click(await screen.findByRole('menuitemradio', { name: 'Mega menu' }))
    // The toast and its screen-reader announcement carry the same text.
    expect((await screen.findAllByText('Menu layout saved')).length).toBeGreaterThan(0)
    expect(writes.at(-1)).toEqual(['PUT', 'me/settings/ui.layout', { value: 'mega' }])
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })
    fireEvent.click(await screen.findByRole('button', { name: 'Explore' }))
    expect(await screen.findByText('Sections')).toBeInTheDocument()
    fireEvent.mouseEnter(screen.getByRole('button', { name: /Projects/ }))
    expect(screen.queryByRole('link', { name: /Alpha/ })).toBeNull()  // hover does not switch
    fireEvent.click(screen.getByRole('button', { name: /Projects/ }))
    expect(await screen.findByRole('link', { name: /Alpha/ })).toBeInTheDocument()
  })

  it('keeps the mega menu open until its close button, or a destination, is used', async () => {
    savePreference('ui.layout', 'mega')
    shell()
    fireEvent.click(await screen.findByRole('button', { name: 'Explore' }))
    expect(await screen.findByRole('region', { name: 'Explore' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close the menu' })).toHaveFocus()
    fireEvent.pointerDown(screen.getByText('page-body'))
    fireEvent.click(screen.getByText('page-body'))
    fireEvent.click(screen.getByRole('button', { name: 'Explore' }))
    expect(screen.getByRole('region', { name: 'Explore' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close the menu' }))
    expect(screen.queryByRole('region', { name: 'Explore' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Explore' }))
    const panel = await screen.findByRole('region', { name: 'Explore' })
    fireEvent.click(within(panel).getByRole('link', { name: /Results/ }))
    expect(screen.queryByRole('region', { name: 'Explore' })).not.toBeInTheDocument()
  })

  it('changes the language of the whole page at once, without a reload', async () => {
    shell()
    await screen.findByRole('link', { name: 'Dashboard' })
    fireEvent.click(screen.getByRole('button', { name: /language/i }))
    expect(await screen.findByRole('link', { name: 'แดชบอร์ด' })).toBeInTheDocument()
    expect(screen.getByText('page-body')).toBeInTheDocument()
    expect(writes.at(-1)).toEqual(['PUT', 'me/settings/ui.locale', { value: 'th' }])
    expect(within(document.body).queryByRole('link', { name: 'Dashboard' })).toBeNull()
  })
})
