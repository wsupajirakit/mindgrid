import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { ApiKeysPage } from './components/ApiKeysPage.tsx'

describe('api keys page', () => {
  it('rotates a key after a confirm and shows the new private key once to copy', async () => {
    renderApp(<ApiKeysPage owners={[]} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Rotate' }))
    const ask = await screen.findByRole('alertdialog')
    expect(ask).toHaveTextContent('Rotate “ci”?')
    fireEvent.click(within(ask).getByRole('button', { name: 'Rotate' }))
    expect(await screen.findByText('New key made: copy it now')).toBeInTheDocument()
    expect(writes[0]?.slice(0, 2)).toEqual(['POST', 'admin/api-keys/k1/rotate'])
    expect(await screen.findByDisplayValue('-----BEGIN PRIVATE KEY-----NEW'))
      .toBeInTheDocument()
  })
})
