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

export interface DownloadedFile {
  blob: Blob
  filename: string | null
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

async function resolveTarget(token?: string): Promise<{
  baseUrl: string
  headers: Record<string, string>
}> {
  await initializeDesktopConnection()
  const desktopConnection = getDesktopConnection()
  const headers: Record<string, string> = {}
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`
  }
  if (desktopConnection !== null) {
    headers['X-Delta-Desktop-Capability'] = desktopConnection.capability
  }
  return {
    baseUrl: desktopConnection?.apiBaseUrl ?? DEVELOPMENT_API_BASE_URL,
    headers,
  }
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  const { baseUrl, headers } = await resolveTarget(options.token)
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function apiUpload<T>(
  path: string,
  options: { token?: string; formData: FormData; method?: string },
): Promise<T> {
  const { baseUrl, headers } = await resolveTarget(options.token)
  // Content-Type é deixado para o navegador: ele precisa gerar o boundary do
  // multipart, e defini-lo aqui quebraria a leitura do corpo pelo servidor.
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? 'POST',
    headers,
    body: options.formData,
  })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }
  return (await response.json()) as T
}

export async function apiDownload(
  path: string,
  options: { token?: string } = {},
): Promise<DownloadedFile> {
  const { baseUrl, headers } = await resolveTarget(options.token)
  const response = await fetch(`${baseUrl}${path}`, { method: 'GET', headers })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }
  return {
    blob: await response.blob(),
    filename: parseContentDispositionFilename(
      response.headers.get('Content-Disposition'),
    ),
  }
}

export function parseContentDispositionFilename(
  header: string | null,
): string | null {
  if (header === null) return null

  // `filename*` (RFC 5987) preserva acentos e vem primeiro por ser o mais fiel.
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (encoded !== null) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      // Um valor malformado cai no `filename` simples abaixo.
    }
  }

  const plain = /filename="([^"]*)"/i.exec(header)
  return plain !== null && plain[1] !== '' ? plain[1] : null
}
