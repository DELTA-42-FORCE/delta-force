import type { DownloadedFile } from '../lib/apiClient'
import type { DocumentOpenLocation } from '../lib/desktopShell'

export interface ClientDocument {
  id: string
  client_folder_id: string
  original_filename: string
  media_type: string
  byte_size: number
  checksum_sha256: string
  stored_at: string
  title: string | null
  category: string | null
  notes: string | null
  status: DocumentStatus | null
}

export type DocumentStatus =
  'pending' | 'received_regular' | 'incorrect_incomplete'

export interface DocumentCursor {
  stored_at: string
  id: string
}

export interface ClientDocumentPage {
  items: ClientDocument[]
  nextCursor: DocumentCursor | null
}

interface DocumentListResponse {
  items: ClientDocument[]
  next_cursor: DocumentCursor | null
}

export interface DocumentAnnotations {
  title?: string
  category?: string
  notes?: string
}

export type AuthenticatedGet = <T>(path: string) => Promise<T>
export type AuthenticatedRequest = <T>(
  path: string,
  options: { method: string; body?: unknown },
) => Promise<T>
export type AuthenticatedUpload = <T>(
  path: string,
  file: File,
  metadataHeaders?: Record<string, string>,
) => Promise<T>
export type AuthenticatedDownload = (path: string) => Promise<DownloadedFile>
export type AuthenticatedOpenDocument = (options: {
  path: string
  clientId: string
  documentId: string
  filename: string
}) => Promise<DocumentOpenLocation>

export async function listClientDocuments(
  authenticatedGet: AuthenticatedGet,
  options: {
    clientId: string
    limit: number
    cursor?: DocumentCursor | null
  },
): Promise<ClientDocumentPage> {
  const query = new URLSearchParams({ limit: String(options.limit) })
  if (options.cursor != null) {
    query.set('before_stored_at', options.cursor.stored_at)
    query.set('before_id', options.cursor.id)
  }

  const response = await authenticatedGet<DocumentListResponse>(
    `/clients/${options.clientId}/documents?${query.toString()}`,
  )
  return { items: response.items, nextCursor: response.next_cursor }
}

export async function attachClientDocument(
  authenticatedUpload: AuthenticatedUpload,
  options: {
    clientId: string
    file: File
    annotations?: DocumentAnnotations
  },
): Promise<ClientDocument> {
  const metadataHeaders: Record<string, string> = {
    'X-Delta-Document-Filename': encodeURIComponent(options.file.name),
  }
  // Os valores ficam fora da URL e usam somente ASCII nos headers. Anotações em
  // branco não são enviadas: nenhuma delas é obrigatória.
  for (const [field, value] of Object.entries(options.annotations ?? {})) {
    if (typeof value === 'string' && value.trim() !== '') {
      const headerName =
        field === 'title'
          ? 'X-Delta-Document-Title'
          : field === 'category'
            ? 'X-Delta-Document-Category'
            : 'X-Delta-Document-Notes'
      metadataHeaders[headerName] = encodeURIComponent(value)
    }
  }

  return authenticatedUpload<ClientDocument>(
    `/clients/${options.clientId}/documents`,
    options.file,
    metadataHeaders,
  )
}

export async function updateClientDocumentStatus(
  authenticatedRequest: AuthenticatedRequest,
  options: {
    clientId: string
    documentId: string
    status: DocumentStatus | null
  },
): Promise<ClientDocument> {
  return authenticatedRequest<ClientDocument>(
    `/clients/${options.clientId}/documents/${options.documentId}/status`,
    { method: 'PATCH', body: { status: options.status } },
  )
}

export async function exportClientDocument(
  authenticatedDownload: AuthenticatedDownload,
  options: { clientId: string; documentId: string },
): Promise<DownloadedFile> {
  return authenticatedDownload(
    `/clients/${options.clientId}/documents/${options.documentId}/content`,
  )
}

export async function openClientDocument(
  authenticatedOpenDocument: AuthenticatedOpenDocument,
  options: { clientId: string; documentId: string; filename: string },
): Promise<DocumentOpenLocation> {
  return authenticatedOpenDocument({
    path: `/clients/${options.clientId}/documents/${options.documentId}/content`,
    ...options,
  })
}
