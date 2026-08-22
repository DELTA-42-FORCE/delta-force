export interface AuditEvent {
  occurred_at: string
  action: string
  result: string
}

export interface AuditCursor {
  occurred_at: string
  id: string
}

export interface AuditEventPage {
  items: AuditEvent[]
  nextCursor: AuditCursor | null
}

interface AuditEventListResponse {
  items: AuditEvent[]
  next_cursor: AuditCursor | null
}

export type AuthenticatedGet = <T>(path: string) => Promise<T>

export async function listAuditEvents(
  authenticatedGet: AuthenticatedGet,
  options: { limit: number; cursor?: AuditCursor | null },
): Promise<AuditEventPage> {
  const query = new URLSearchParams({ limit: String(options.limit) })
  if (options.cursor != null) {
    query.set('before_occurred_at', options.cursor.occurred_at)
    query.set('before_id', options.cursor.id)
  }

  const response = await authenticatedGet<AuditEventListResponse>(
    `/audit/events?${query.toString()}`,
  )
  return {
    items: response.items.map(({ occurred_at, action, result }) => ({
      occurred_at,
      action,
      result,
    })),
    nextCursor: response.next_cursor,
  }
}

export async function listRecentAuditEvents(
  authenticatedGet: AuthenticatedGet,
): Promise<AuditEvent[]> {
  return (await listAuditEvents(authenticatedGet, { limit: 5 })).items
}
