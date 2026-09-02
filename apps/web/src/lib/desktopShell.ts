import { invoke } from '@tauri-apps/api/core'

import type { DownloadedFile } from './apiClient'

/** Onde o documento foi aberto para consulta. */
export type DocumentOpenLocation = 'desktop-app' | 'browser-tab'

function isTauriRuntime(): boolean {
  return '__TAURI_INTERNALS__' in window
}

function encodeBase64(bytes: Uint8Array): string {
  // Conversão em blocos: evita estourar o limite de argumentos de
  // `String.fromCharCode` em documentos maiores antes do `btoa`.
  let binary = ''
  const CHUNK = 0x8000
  for (let offset = 0; offset < bytes.length; offset += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + CHUNK))
  }
  return btoa(binary)
}

/**
 * Abre a cópia autorizada para consulta imediata (#22).
 *
 * No aplicativo Windows, entrega o conteúdo ao shell desktop, que grava uma
 * cópia temporária e a abre no programa padrão do sistema. Fora dele (execução
 * no navegador, em desenvolvimento), abre a cópia em uma nova aba. A gravação
 * privada original nunca sai da área do CRM: o desktop recebe apenas os bytes
 * já baixados desta sessão autenticada.
 */
export async function openDownloadedDocument(
  file: DownloadedFile,
  fallbackName: string,
): Promise<DocumentOpenLocation> {
  const filename = file.filename ?? fallbackName

  if (isTauriRuntime()) {
    const content = new Uint8Array(await file.blob.arrayBuffer())
    await invoke('open_document', {
      request: { filename, contentBase64: encodeBase64(content) },
    })
    return 'desktop-app'
  }

  const url = URL.createObjectURL(file.blob)
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  if (opened === null) {
    URL.revokeObjectURL(url)
    throw new Error('the browser blocked opening the document in a new tab')
  }
  // O object URL precisa sobreviver ao carregamento da nova aba antes de sair.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  return 'browser-tab'
}
