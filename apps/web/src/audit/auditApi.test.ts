import { describe, expect, it, vi } from 'vitest'

import { listAuditEvents, listRecentAuditEvents } from './auditApi'

describe('listRecentAuditEvents', () => {
  it('requests a bounded page and discards internal event fields', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue({
      items: [
        {
          id: 'internal-event-id',
          occurred_at: '2026-08-22T18:30:00Z',
          actor_user_id: 'internal-owner-id',
          action: 'auth.login',
          resource_id: 'internal-resource-id',
          result: 'success',
          context: { route: '/auth/login' },
        },
      ],
      next_cursor: null,
    })

    await expect(listRecentAuditEvents(authenticatedGet)).resolves.toEqual([
      {
        occurred_at: '2026-08-22T18:30:00Z',
        action: 'auth.login',
        result: 'success',
      },
    ])
    expect(authenticatedGet).toHaveBeenCalledWith('/audit/events?limit=5')
  })

  it('encodes both stable cursor fields when loading an older page', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue({
      items: [],
      next_cursor: null,
    })

    await listAuditEvents(authenticatedGet, {
      limit: 20,
      filters: { action: 'auth.login', result: 'denied' },
      cursor: {
        occurred_at: '2026-08-22T18:30:00Z',
        id: '00000000-0000-0000-0000-000000000002',
      },
    })

    expect(authenticatedGet).toHaveBeenCalledWith(
      '/audit/events?limit=20&action=auth.login&result=denied&before_occurred_at=2026-08-22T18%3A30%3A00Z&before_id=00000000-0000-0000-0000-000000000002',
    )
  })
})
