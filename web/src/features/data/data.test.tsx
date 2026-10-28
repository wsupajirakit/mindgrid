import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { writes } from '../../testing/mocks/handlers.ts'
import { renderApp } from '../../testing/render.tsx'
import { ConnectorsPanel } from './components/ConnectorsPanel.tsx'
import { DataPanel } from './components/DataPanel.tsx'
import { pickOption } from '../../testing/select.ts'

describe('data', () => {
  it('creates a connector from a template in a modal', async () => {
    renderApp(<ConnectorsPanel projectId="p1" />)
    expect(await screen.findByText('No connectors yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'New connector' }))
    const form = await screen.findByRole('dialog')
    await pickOption(within(form).getByLabelText('Start from'), 'z-service')
    expect(within(form).getByLabelText('Name')).toHaveValue('zservice')
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Connector saved')).toBeInTheDocument()
    expect(writes[0]).toEqual(['PUT', 'projects/p1/connectors/zservice',
      { spec: { url: 'https://z.test/x' }, every_minutes: 60 }])
  })

  it('uploads a dataset in a modal', async () => {
    renderApp(<DataPanel projectId="p1" />)
    expect(await screen.findByText('No datasets yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Upload dataset' }))
    const form = await screen.findByRole('dialog')
    const send = within(form).getByRole('button', { name: 'Upload' })
    fireEvent.change(within(form).getByLabelText('Dataset name'), { target: { value: 'Prices' } })
    expect(send).toBeDisabled()
    fireEvent.change(within(form).getByLabelText(/^file/i),
      { target: { files: [new File(['a,b\n1,2\n'], 'p.csv', { type: 'text/csv' })] } })
    fireEvent.click(send)
    expect(await screen.findByText('Dataset uploaded')).toBeInTheDocument()
    expect(writes[0]?.slice(0, 2)).toEqual(['POST', 'projects/p1/datasets/prices'])
  })
})
