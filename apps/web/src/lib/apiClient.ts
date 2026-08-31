import {
  getDesktopConnection,
  initializeDesktopConnection,
} from './desktopConnection'

const DEVELOPMENT_API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
  } catch {
    // Uma resposta sem JSON usa a mensagem HTTP genérica.
  }
  return response.statusText
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  await initializeDesktopConnection()
  const desktopConnection = getDesktopConnection()
  const headers: Record<string, string> = {}
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (options.token !== undefined) {
    headers.Authorization = `Bearer ${options.token}`
  }
  if (desktopConnection !== null) {
    headers['X-Delta-Desktop-Capability'] = desktopConnection.capability
  }

  const response = await fetch(
    `${desktopConnection?.apiBaseUrl ?? DEVELOPMENT_API_BASE_URL}${path}`,
    {
      method: options.method ?? 'GET',
      headers,
      body:
        options.body !== undefined ? JSON.stringify(options.body) : undefined,
    },
  )

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
