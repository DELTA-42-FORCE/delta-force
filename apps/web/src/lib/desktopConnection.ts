import { invoke } from '@tauri-apps/api/core'

export interface DesktopConnection {
  apiBaseUrl: string
  capability: string
}

function isTauriRuntime(): boolean {
  return '__TAURI_INTERNALS__' in window
}

let connection: DesktopConnection | null = null
let initialization: Promise<void> | null = null

export function initializeDesktopConnection(): Promise<void> {
  if (!isTauriRuntime()) return Promise.resolve()
  if (initialization !== null) return initialization

  initialization = invoke<DesktopConnection>('desktop_connection').then(
    (receivedConnection) => {
      if (
        !receivedConnection.apiBaseUrl.startsWith('http://127.0.0.1:') ||
        !receivedConnection.capability
      ) {
        throw new Error('desktop runtime returned an invalid connection')
      }
      connection = receivedConnection
    },
  )
  return initialization
}

export function getDesktopConnection(): DesktopConnection | null {
  return connection
}
