import type { AuthenticatedRequest } from '../clients/clientsApi'

/**
 * Cliente HTTP da importação do acervo legado (#45).
 *
 * São dois passos deliberados: a prévia é um ensaio sem escrita, para o
 * proprietário revisar; a importação copia apenas os arquivos elegíveis. Ambos
 * reaproveitam o `authenticatedRequest` já usado no resto do app.
 */

export type LegacyImportItemStatus =
  | 'matched'
  | 'client_not_found'
  | 'client_ambiguous'
  | 'unsupported_format'
  | 'unreadable'

export interface LegacyImportItem {
  relative_path: string
  client_folder_name: string | null
  status: LegacyImportItemStatus
  media_type: string | null
  matched_client_id: string | null
}

export interface LegacyImportPreview {
  source_path: string
  summary: Record<string, number>
  items: LegacyImportItem[]
}

export type LegacyImportOutcome =
  | 'imported'
  | 'duplicate'
  | 'skipped'
  | 'unsupported_format'
  | 'unreadable'
  | 'insufficient_space'
  | 'failed'

export interface LegacyImportResultItem {
  relative_path: string
  client_folder_name: string | null
  outcome: LegacyImportOutcome
  document_id: string | null
}

export interface LegacyImportResult {
  source_path: string
  summary: Record<string, number>
  items: LegacyImportResultItem[]
}

export async function previewLegacyImport(
  authenticatedRequest: AuthenticatedRequest,
  sourcePath: string,
): Promise<LegacyImportPreview> {
  return authenticatedRequest<LegacyImportPreview>('/imports/legacy/preview', {
    method: 'POST',
    body: { source_path: sourcePath },
  })
}

export async function importLegacyArchive(
  authenticatedRequest: AuthenticatedRequest,
  sourcePath: string,
): Promise<LegacyImportResult> {
  return authenticatedRequest<LegacyImportResult>('/imports/legacy', {
    method: 'POST',
    body: { source_path: sourcePath },
  })
}
