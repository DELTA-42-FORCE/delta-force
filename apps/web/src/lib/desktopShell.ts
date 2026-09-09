import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'

import type { DownloadedFile } from './apiClient'

/** Onde o documento foi aberto para consulta. */
export type DocumentOpenLocation = 'desktop-app' | 'browser-tab'

export function isTauriRuntime(): boolean {
  return '__TAURI_INTERNALS__' in window
}

/**
 * Abre o seletor nativo de pasta do Windows para a importação do acervo (#45).
 *
 * O WebView não tem acesso ao sistema de arquivos; o shell nativo apresenta o
 * diálogo e devolve o caminho absoluto escolhido. Retorna `null` quando o
 * proprietário cancela a seleção.
 */
export async function pickImportFolder(): Promise<string | null> {
  const selected = await open({
    directory: true,
    multiple: false,
    title: 'Selecione a pasta do acervo legado',
  })
  return typeof selected === 'string' ? selected : null
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
