import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../../testing/render.tsx'
import { AuditLog } from './components/AuditLog.tsx'

describe('audit log', () => {
  it('names who did it and who it was about, never a bare user id', async () => {
    renderApp(<AuditLog projectId="p1" />)
    expect(await screen.findByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    expect(screen.queryByText('u1')).not.toBeInTheDocument()
    expect(screen.queryByText(/user u2/)).not.toBeInTheDocument()
  })
})
