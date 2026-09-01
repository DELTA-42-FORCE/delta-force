export interface ClientFolder {
  id: string
  display_name: string
  profile_data: Record<string, string>
  created_at: string
  updated_at: string
}

export interface ClientCursor {
  display_name: string
  id: string
}

export interface ClientFolderPage {
  items: ClientFolder[]
  nextCursor: ClientCursor | null
}

interface ClientFolderListResponse {
  items: ClientFolder[]
  next_cursor: ClientCursor | null
}

export type AuthenticatedGet = <T>(path: string) => Promise<T>
export type AuthenticatedRequest = <T>(
  path: string,
  options: { method: string; body?: unknown },
) => Promise<T>

export async function listClientFolders(
  authenticatedGet: AuthenticatedGet,
  options: {
    limit: number
    query?: string | null
    cursor?: ClientCursor | null
  },
): Promise<ClientFolderPage> {
  const query = new URLSearchParams({ limit: String(options.limit) })
  if (options.query) {
    query.set('query', options.query)
  }
  if (options.cursor != null) {
    query.set('before_display_name', options.cursor.display_name)
    query.set('before_id', options.cursor.id)
  }

  const response = await authenticatedGet<ClientFolderListResponse>(
    `/clients?${query.toString()}`,
  )
  return {
    items: response.items,
    nextCursor: response.next_cursor,
  }
}

export async function getClientFolder(
  authenticatedGet: AuthenticatedGet,
  id: string,
): Promise<ClientFolder> {
  return authenticatedGet<ClientFolder>(`/clients/${id}`)
}

export async function createClientFolder(
  authenticatedRequest: AuthenticatedRequest,
  input: { display_name: string; profile_data?: Record<string, string> },
): Promise<ClientFolder> {
  return authenticatedRequest<ClientFolder>('/clients', {
    method: 'POST',
    body: input,
  })
}

export async function updateClientFolder(
  authenticatedRequest: AuthenticatedRequest,
  id: string,
  input: { display_name: string; profile_data?: Record<string, string> },
): Promise<ClientFolder> {
  return authenticatedRequest<ClientFolder>(`/clients/${id}`, {
    method: 'PUT',
    body: input,
  })
}
