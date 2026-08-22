import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AuditCursor, AuditEventPage } from './auditApi'
import { AuditHistoryPage } from './AuditHistoryPage'

const CURSOR: AuditCursor = {
  occurred_at: '2026-08-22T18:30:00Z',
  id: '00000000-0000-0000-0000-000000000002',
}

function page(action: string, nextCursor: AuditCursor | null): AuditEventPage {
  return {
    items: [
      {
        occurred_at: '2026-08-22T18:30:00Z',
        action,
        result: 'success',
      },
    ],
    nextCursor,
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('AuditHistoryPage', () => {
  it('loads older pages with the stable cursor and keeps prior events', async () => {
    const loadPage = vi
      .fn<(cursor: AuditCursor | null) => Promise<AuditEventPage>>()
      .mockResolvedValueOnce(page('auth.login', CURSOR))
      .mockResolvedValueOnce(page('auth.logout', null))
    const user = userEvent.setup()

    render(<AuditHistoryPage loadPage={loadPage} onBack={() => undefined} />)

    expect(await screen.findByText('Entrada realizada')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByText('Saída realizada')).toBeVisible()
    expect(screen.getByText('Entrada realizada')).toBeVisible()
    expect(loadPage).toHaveBeenNthCalledWith(1, null)
    expect(loadPage).toHaveBeenNthCalledWith(2, CURSOR)
    expect(
      screen.queryByRole('button', { name: 'Carregar mais' }),
    ).not.toBeInTheDocument()
  })

  it('shows an explicit empty state', async () => {
    render(
      <AuditHistoryPage
        loadPage={() => Promise.resolve({ items: [], nextCursor: null })}
        onBack={() => undefined}
      />,
    )

    expect(
      await screen.findByText('Nenhuma atividade registrada ainda.'),
    ).toBeVisible()
  })

  it('retries an initial failure', async () => {
    const loadPage = vi
      .fn<(cursor: AuditCursor | null) => Promise<AuditEventPage>>()
      .mockRejectedValueOnce(new Error('service unavailable'))
      .mockResolvedValueOnce({ items: [], nextCursor: null })
    const user = userEvent.setup()
    render(<AuditHistoryPage loadPage={loadPage} onBack={() => undefined} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível consultar o histórico agora.',
    )
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(2))
    expect(
      await screen.findByText('Nenhuma atividade registrada ainda.'),
    ).toBeVisible()
  })

  it('preserves events and retries when loading an older page fails', async () => {
    const loadPage = vi
      .fn<(cursor: AuditCursor | null) => Promise<AuditEventPage>>()
      .mockResolvedValueOnce(page('auth.login', CURSOR))
      .mockRejectedValueOnce(new Error('service unavailable'))
      .mockResolvedValueOnce(page('auth.logout', null))
    const user = userEvent.setup()
    render(<AuditHistoryPage loadPage={loadPage} onBack={() => undefined} />)

    expect(await screen.findByText('Entrada realizada')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar os registros anteriores.',
    )
    expect(screen.getByText('Entrada realizada')).toBeVisible()

    await user.click(
      screen.getByRole('button', { name: 'Tentar carregar novamente' }),
    )
    expect(await screen.findByText('Saída realizada')).toBeVisible()
    expect(loadPage).toHaveBeenCalledTimes(3)
  })
})
