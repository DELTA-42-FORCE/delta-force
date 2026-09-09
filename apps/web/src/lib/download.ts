import type { DownloadedFile } from './apiClient'

/**
 * Entrega ao usuário um arquivo já baixado do serviço local, salvando-o pelo
 * navegador. Usa o nome sugerido pelo servidor (Content-Disposition) e recorre
 * ao `fallbackName` quando ele não vem. O object URL é sempre revogado.
 */
export function saveDownloadedFile(
  file: DownloadedFile,
  fallbackName: string,
): void {
  const url = URL.createObjectURL(file.blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = file.filename ?? fallbackName
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}
