import { ApiError } from '../lib/apiClient'

export interface BackupStatus {
  interval_days: number | null
  last_backup_at: string | null
  reminder_due: boolean
  recovery_required: boolean
}

export interface BackupEstimate {
  required_bytes: number
  available_bytes: number
  local_required_bytes: number
  local_available_bytes: number
}

export interface RestorePreview {
  preview_token: string
  current_records: Record<string, number>
  candidate_records: Record<string, number>
  replacement_required: boolean
  expires_in_seconds: number
}

export function backupFailure(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.message) {
      case 'backup_preview_expired':
        return 'A revisão expirou ou os dados mudaram. Valide o backup novamente.'
      case 'backup_confirmation_required':
        return 'Confira a senha de acesso ao CRM e digite RESTAURAR para confirmar.'
      case 'backup_insufficient_space':
        return 'Não há espaço suficiente no computador para validar este backup.'
      case 'backup_restart_required':
        return 'Feche e abra o CRM para concluir a recuperação com segurança.'
      case 'backup_requires_desktop':
        return 'Abra o aplicativo Windows para acessar o backup.'
    }
  }
  return 'Não foi possível concluir. Confira o HD, o espaço disponível, o arquivo e a senha do backup; depois tente novamente.'
}

export function validBackupPassphrase(value: string): boolean {
  const bytes = new TextEncoder().encode(value.normalize('NFC')).length
  return bytes >= 12 && bytes <= 1024
}

export function formatBytes(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits: 1,
    style: 'unit',
    unit: value >= 1024 ** 3 ? 'gigabyte' : 'megabyte',
  }).format(value / (value >= 1024 ** 3 ? 1024 ** 3 : 1024 ** 2))
}
