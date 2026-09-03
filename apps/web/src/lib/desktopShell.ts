import { invoke } from '@tauri-apps/api/core'

import type { DownloadedFile } from './apiClient'

/** Onde o documento foi aberto para consulta. */
export type DocumentOpenLocation = 'desktop-app' | 'browser-tab'

export function isTauriRuntime(): boolean {
  return '__TAURI_INTERNALS__' in window
}

/**
 * Solicita ao shell a abertura de um documento no aplicativo Windows (#22).
 *
 * O WebView nunca materializa o conteúdo: o shell obtém a cópia autorizada da
 * API local por streaming e a grava no cache privado de sua execução.
 */
export async function openDesktopDocument(options: {
  clientId: string
  documentId: string
  filename: string
  sessionToken: string
}): Promise<DocumentOpenLocation> {
  await invoke('open_document', {
    request: options,
  })
  return 'desktop-app'
}

/** Abre a cópia já baixada somente na execução pelo navegador. */
export function openDownloadedDocument(
  file: DownloadedFile,
): DocumentOpenLocation {
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
