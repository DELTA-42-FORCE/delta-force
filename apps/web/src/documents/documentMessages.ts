import { ApiError } from '../lib/apiClient'

/**
 * Traduz a falha do servidor em uma frase acionável para o proprietário.
 *
 * A issue #22 exige mensagem clara por causa: formato, conteúdo, nome, falta
 * de espaço, acesso negado e falha de armazenamento. O texto do servidor é
 * técnico e em inglês, então ele só aparece como complemento do 422, onde
 * indica qual campo precisa ser corrigido.
 */
export function describeAttachFailure(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente de novo.'
  }

  switch (error.status) {
    case 401:
      return 'Sua sessão expirou. Entre novamente para anexar documentos.'
    case 403:
      return 'Seu acesso a esta pasta foi negado.'
    case 404:
      return 'Esta pasta de cliente não existe mais. Atualize a lista e tente de novo.'
    case 415:
      return 'Arquivo recusado: o conteúdo não é um PDF ou JPEG íntegro. Verifique se o arquivo não está corrompido ou incompleto.'
    case 422:
      return `Não foi possível aceitar este arquivo: ${error.message}`
    case 507:
      return 'Não há espaço livre suficiente neste computador para guardar o documento. Libere espaço no disco e tente novamente.'
    default:
      return 'Falha ao gravar o documento no armazenamento local. Nada foi salvo pela metade — tente novamente.'
  }
}

export function describeExportFailure(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente de novo.'
  }

  switch (error.status) {
    case 401:
      return 'Sua sessão expirou. Entre novamente para exportar o documento.'
    case 403:
      return 'Seu acesso a este documento foi negado.'
    case 404:
      return 'Documento não encontrado nesta pasta.'
    default:
      return 'O arquivo não pôde ser lido no armazenamento local. Ele pode ter sido movido ou removido fora do CRM.'
  }
}

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`

  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < UNITS.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1).replace('.', ',')} ${UNITS[unitIndex]}`
}

export function describeMediaType(mediaType: string): string {
  if (mediaType === 'application/pdf') return 'PDF'
  if (mediaType === 'image/jpeg') return 'JPEG'
  return mediaType
}
