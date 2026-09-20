import { apiFetch } from '../lib/apiClient'

export interface BackupStatus {
  last_successful_at: string | null
  reminder_due: boolean
}

export interface BackupCreationResult {
  filename: string
  created_at: string
  byte_size: number
  document_count: number
}

export interface RestoreStagingResult {
  backup_created_at: string
  document_count: number
  requires_restart: boolean
}

type AuthenticatedGet = <T>(path: string) => Promise<T>
type AuthenticatedRequest = <T>(
  path: string,
  options: { method: string; body?: unknown },
) => Promise<T>

export function getBackupStatus(
  request: AuthenticatedGet,
): Promise<BackupStatus> {
  return request<BackupStatus>('/backups/status')
}

export function createBackup(
  request: AuthenticatedRequest,
  input: { destination_directory: string; passphrase: string },
): Promise<BackupCreationResult> {
  return request<BackupCreationResult>('/backups', {
    method: 'POST',
    body: input,
  })
}

export function stageBackupRestore(input: {
  source_file: string
  passphrase: string
}): Promise<RestoreStagingResult> {
  return apiFetch<RestoreStagingResult>('/backups/restore', {
    method: 'POST',
    body: input,
  })
}
