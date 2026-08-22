import { describe, expect, it, vi } from 'vitest'

import { listRecentAuditEvents } from './auditApi'

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
})
