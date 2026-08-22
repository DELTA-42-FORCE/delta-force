import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RecentActivity } from './RecentActivity'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('RecentActivity', () => {
  it('shows only safe, friendly fields from recent audit events', async () => {
    const loadEvents = vi.fn().mockResolvedValue([
      {
        occurred_at: '2026-08-22T18:30:00Z',
        action: 'auth.login',
        result: 'success',
        resource_id: 'internal-owner-id',
        context: { ip_address: 'sensitive-value' },
      },
      {
        occurred_at: 'invalid-date',
        action: 'future.unknown_action',
        result: 'future-result',
      },
    ])

    const onViewAll = vi.fn()
    const user = userEvent.setup()
    render(<RecentActivity loadEvents={loadEvents} onViewAll={onViewAll} />)

    expect(await screen.findByText('Entrada realizada')).toBeVisible()
    expect(screen.getByText('Concluída')).toBeVisible()
    expect(screen.getByText('Atividade registrada')).toBeVisible()
    expect(screen.getByText('Horário indisponível')).toBeVisible()
    expect(screen.queryByText('internal-owner-id')).not.toBeInTheDocument()
    expect(screen.queryByText('sensitive-value')).not.toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Ver histórico completo' }),
    )
    expect(onViewAll).toHaveBeenCalledOnce()
  })

  it('shows an explicit empty state', async () => {
    render(
      <RecentActivity
        loadEvents={() => Promise.resolve([])}
        onViewAll={() => undefined}
      />,
    )

    expect(
      await screen.findByText('Nenhuma atividade registrada ainda.'),
    ).toBeVisible()
  })

  it('shows an error and retries the request', async () => {
    const loadEvents = vi
      .fn<() => Promise<[]>>()
      .mockRejectedValueOnce(new Error('service unavailable'))
      .mockResolvedValueOnce([])
    const user = userEvent.setup()
    render(
      <RecentActivity loadEvents={loadEvents} onViewAll={() => undefined} />,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível consultar as atividades agora.',
    )
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(loadEvents).toHaveBeenCalledTimes(2))
    expect(
      await screen.findByText('Nenhuma atividade registrada ainda.'),
    ).toBeVisible()
  })
})
