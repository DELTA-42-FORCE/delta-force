import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DownloadedFile } from './apiClient'

function file(bytes: number[], filename: string | null): DownloadedFile {
  return { blob: new Blob([new Uint8Array(bytes)]), filename }
}

afterEach(() => {
  vi.resetModules()
  vi.doUnmock('@tauri-apps/api/core')
  vi.doUnmock('@tauri-apps/plugin-dialog')
  delete (window as Window & { __TAURI_INTERNALS__?: unknown })
    .__TAURI_INTERNALS__
  vi.restoreAllMocks()
})

describe('desktop shell open', () => {
  it('selects a backup directory and filters the native restore file picker', async () => {
    const open = vi
      .fn()
      .mockResolvedValueOnce('E:\\Backup')
      .mockResolvedValueOnce(null)
    vi.doMock('@tauri-apps/plugin-dialog', () => ({ open }))
    const shell = await import('./desktopShell')
    expect(await shell.pickBackupFolder()).toBe('E:\\Backup')
    expect(open).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ directory: true, multiple: false }),
    )
    expect(await shell.pickBackupFile()).toBeNull()
    expect(open).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        directory: false,
        multiple: false,
        filters: [{ name: 'Backup Delta Force CRM', extensions: ['dfcrmbak'] }],
      }),
    )
  })
  it('asks the desktop shell to stream the authorized copy inside Tauri', async () => {
    ;(
      window as Window & { __TAURI_INTERNALS__?: unknown }
    ).__TAURI_INTERNALS__ = {}
    const invoke = vi.fn().mockResolvedValue(undefined)
    vi.doMock('@tauri-apps/api/core', () => ({ invoke }))
    const shell = await import('./desktopShell')

    const location = await shell.openDesktopDocument({
      clientId: '00000000-0000-0000-0000-0000000000aa',
      documentId: '00000000-0000-0000-0000-000000000001',
      filename: 'contrato.pdf',
      sessionToken: 'session-only-in-memory',
    })

    expect(location).toBe('desktop-app')
    expect(invoke).toHaveBeenCalledTimes(1)
    const [command, payload] = invoke.mock.calls[0]
    expect(command).toBe('open_document')
    expect(payload.request.filename).toBe('contrato.pdf')
    expect(payload.request.documentId).toBe(
      '00000000-0000-0000-0000-000000000001',
    )
    // Não há Blob nem Base64 no IPC: o Tauri baixa por streaming.
    expect(payload.request).not.toHaveProperty('contentBase64')
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

    const location = shell.openDownloadedDocument(
      file([0x25, 0x50], 'contrato.pdf'),
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

    await expect(() =>
      shell.openDownloadedDocument(file([0x25], 'contrato.pdf')),
    ).toThrow(/blocked/)
    // Uma aba bloqueada não pode deixar o object URL vazando.
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
