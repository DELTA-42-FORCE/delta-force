import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DownloadedFile } from './apiClient'

function file(bytes: number[], filename: string | null): DownloadedFile {
  return { blob: new Blob([new Uint8Array(bytes)]), filename }
}

afterEach(() => {
  vi.resetModules()
  vi.doUnmock('@tauri-apps/api/core')
  delete (window as Window & { __TAURI_INTERNALS__?: unknown })
    .__TAURI_INTERNALS__
  vi.restoreAllMocks()
})

describe('desktop shell open', () => {
  it('hands the copy to the desktop shell inside the Tauri runtime', async () => {
    ;(
      window as Window & { __TAURI_INTERNALS__?: unknown }
    ).__TAURI_INTERNALS__ = {}
    const invoke = vi.fn().mockResolvedValue(undefined)
    vi.doMock('@tauri-apps/api/core', () => ({ invoke }))
    const shell = await import('./desktopShell')

    const location = await shell.openDownloadedDocument(
      file([0x25, 0x50, 0x44, 0x46], 'contrato.pdf'),
      'fallback.pdf',
    )

    expect(location).toBe('desktop-app')
    expect(invoke).toHaveBeenCalledTimes(1)
    const [command, payload] = invoke.mock.calls[0]
    expect(command).toBe('open_document')
    expect(payload.request.filename).toBe('contrato.pdf')
    // "%PDF" em base64: o shell recebe os bytes já baixados, não um caminho.
    expect(payload.request.contentBase64).toBe('JVBERg==')
  })

  it('uses the server filename and falls back to the given name when absent', async () => {
    ;(
      window as Window & { __TAURI_INTERNALS__?: unknown }
    ).__TAURI_INTERNALS__ = {}
    const invoke = vi.fn().mockResolvedValue(undefined)
    vi.doMock('@tauri-apps/api/core', () => ({ invoke }))
    const shell = await import('./desktopShell')

    await shell.openDownloadedDocument(file([0x25], null), 'fallback.pdf')

    expect(invoke.mock.calls[0][1].request.filename).toBe('fallback.pdf')
  })

  it('opens the copy in a new tab outside the desktop runtime', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
    const open = vi
      .spyOn(window, 'open')
      .mockReturnValue({} as ReturnType<typeof window.open>)
    const shell = await import('./desktopShell')

    const location = await shell.openDownloadedDocument(
      file([0x25, 0x50], 'contrato.pdf'),
      'fallback.pdf',
    )

    expect(location).toBe('browser-tab')
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(open).toHaveBeenCalledWith(
      'blob:mock',
      '_blank',
      'noopener,noreferrer',
    )
  })

  it('reports when the browser blocks the new tab', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    URL.revokeObjectURL = revokeObjectURL
    vi.spyOn(window, 'open').mockReturnValue(null)
    const shell = await import('./desktopShell')

    await expect(
      shell.openDownloadedDocument(
        file([0x25], 'contrato.pdf'),
        'fallback.pdf',
      ),
    ).rejects.toThrow(/blocked/)
    // Uma aba bloqueada não pode deixar o object URL vazando.
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
