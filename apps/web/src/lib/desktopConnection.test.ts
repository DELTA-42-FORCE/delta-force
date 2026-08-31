import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.resetModules()
  vi.doUnmock('@tauri-apps/api/core')
  delete (window as Window & { __TAURI_INTERNALS__?: unknown })
    .__TAURI_INTERNALS__
})

describe('desktop connection bridge', () => {
  it('does nothing outside the Tauri runtime', async () => {
    const bridge = await import('./desktopConnection')

    await bridge.initializeDesktopConnection()

    expect(bridge.getDesktopConnection()).toBeNull()
  })

  it('keeps the capability only in module memory after Tauri IPC', async () => {
    ;(
      window as Window & { __TAURI_INTERNALS__?: unknown }
    ).__TAURI_INTERNALS__ = {}
    const invoke = vi.fn().mockResolvedValue({
      apiBaseUrl: 'http://127.0.0.1:43123',
      capability: 'synthetic-capability',
    })
    vi.doMock('@tauri-apps/api/core', () => ({ invoke }))
    const bridge = await import('./desktopConnection')

    await bridge.initializeDesktopConnection()

    expect(invoke).toHaveBeenCalledWith('desktop_connection')
    expect(bridge.getDesktopConnection()).toEqual({
      apiBaseUrl: 'http://127.0.0.1:43123',
      capability: 'synthetic-capability',
    })
    expect(window.localStorage.length).toBe(0)
  })
})
