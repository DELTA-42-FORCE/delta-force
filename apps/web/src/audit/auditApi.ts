export interface AuditEvent {
  occurred_at: string
  action: string
  result: string
}

interface AuditEventListResponse {
  items: AuditEvent[]
}

export type AuthenticatedGet = <T>(path: string) => Promise<T>

export async function listRecentAuditEvents(
  authenticatedGet: AuthenticatedGet,
): Promise<AuditEvent[]> {
  const response = await authenticatedGet<AuditEventListResponse>(
    '/audit/events?limit=5',
  )
  return response.items.map(({ occurred_at, action, result }) => ({
    occurred_at,
    action,
    result,
  }))
}
