import { ApiError } from '../lib/apiClient'
import type { LegacyImportItemStatus, LegacyImportOutcome } from './importsApi'

/**
 * Rótulos e mensagens da importação do acervo legado (#45).
 *
 * A #45 exige que o proprietário revise a prévia e leia um relatório claro por
 * arquivo, incluindo os itens não importados (sem cliente, formato inválido,
 * quebrado ou sem espaço). O servidor devolve códigos técnicos; aqui eles viram
 * frases curtas em português.
 */

const STATUS_LABELS: Record<LegacyImportItemStatus, string> = {
  matched: 'Cliente identificado',
  client_not_found: 'Sem pasta de cliente correspondente',
  client_ambiguous: 'Cliente ambíguo — revisão manual',
  unsupported_format: 'Formato não suportado',
  unreadable: 'Arquivo ilegível ou corrompido',
}

const OUTCOME_LABELS: Record<LegacyImportOutcome, string> = {
  imported: 'Importado',
  duplicate: 'Duplicado — já existia',
  skipped: 'Ignorado — sem cliente definido',
  unsupported_format: 'Formato não suportado',
  unreadable: 'Arquivo ilegível ou corrompido',
  insufficient_space: 'Sem espaço em disco',
  failed: 'Falhou',
}

const SUMMARY_LABELS: Record<string, string> = {
  ...STATUS_LABELS,
  ...OUTCOME_LABELS,
  total: 'Total de arquivos',
}

export function describeImportStatus(status: LegacyImportItemStatus): string {
  return STATUS_LABELS[status]
}

export function describeImportOutcome(outcome: LegacyImportOutcome): string {
  return OUTCOME_LABELS[outcome]
}

export function describeSummaryKey(key: string): string {
  return SUMMARY_LABELS[key] ?? key
}

export function describeImportFailure(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente de novo.'
  }

  switch (error.status) {
    case 401:
      return 'Sua sessão expirou. Entre novamente para importar o acervo.'
    case 403:
      return 'Seu acesso à importação foi negado.'
    case 422:
      // LegacyImportSourceError: a pasta não existe, não é diretório ou não
      // pôde ser lida. O texto do servidor detalha qual é o problema.
      return `A pasta de origem não pôde ser usada: ${error.message}`
    case 507:
      return 'Não há espaço livre suficiente neste computador para concluir a importação. Libere espaço no disco e tente novamente.'
    default:
      return 'A importação falhou no serviço local. Nenhum arquivo foi gravado pela metade — tente novamente.'
  }
}
