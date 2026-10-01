import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AuthenticatedGet } from '../audit/auditApi'
import type { AuthenticatedRequest } from '../clients/clientsApi'
import type { BackupEstimate, BackupStatus, RestorePreview } from './backupApi'
import { BackupPage } from './BackupPage'

const STATUS: BackupStatus = {
  interval_days: null,
  last_backup_at: null,
  reminder_due: false,
  recovery_required: false,
}

const ESTIMATE: BackupEstimate = {
  required_bytes: 1024,
  available_bytes: 4096,
  local_required_bytes: 1024,
  local_available_bytes: 4096,
}

const PREVIEW: RestorePreview = {
  preview_token: 'preview-sintetico',
  current_records: { clients: 1 },
  candidate_records: { clients: 2 },
  replacement_required: true,
  expires_in_seconds: 600,
}

function makeRequest(
  implementation: (
    path: string,
    options: { method: string; body?: unknown },
  ) => Promise<unknown>,
) {
  const spy =
    vi.fn<
      (
        path: string,
        options: { method: string; body?: unknown },
      ) => Promise<unknown>
    >(implementation)
  const request: AuthenticatedRequest = async <T,>(
    path: string,
    options: { method: string; body?: unknown },
  ) => (await spy(path, options)) as T
  return { request, spy }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderPage(
  options: {
    available?: boolean
    pickFolder?: () => Promise<string | null>
    pickFile?: () => Promise<string | null>
    get?: AuthenticatedGet
    request?: AuthenticatedRequest
  } = {},
) {
  const getSpy = vi.fn(async (path: string): Promise<unknown> => {
    if (path === '/backups/status') return STATUS
    throw new Error(`Unexpected GET ${path}`)
  })
  const get: AuthenticatedGet =
    options.get ?? (async <T,>(path: string) => (await getSpy(path)) as T)
  const defaultRequest = makeRequest(async (path) => {
    if (path === '/backups/estimate') return ESTIMATE
    if (path === '/backups/restore/preview') return PREVIEW
    if (path === '/backups/reminder') return STATUS
    if (path === '/backups') return { completed: true, reminder_updated: true }
    return undefined
  })
  const request = options.request ?? defaultRequest.request
  const onRestored = vi.fn()
  render(
    <BackupPage
      get={get}
      request={request}
      available={options.available ?? true}
      onBack={vi.fn()}
      onRestored={onRestored}
      onBackupCreated={vi.fn()}
      onBusyChange={vi.fn()}
      pickFolder={options.pickFolder}
      pickFile={options.pickFile}
    />,
  )
  return {
    get,
    request,
    onRestored,
    getSpy,
    requestSpy: defaultRequest.spy,
  }
}

describe('BackupPage', () => {
  it('explains that browser backup is unsupported', () => {
    const { getSpy } = renderPage({ available: false })

    expect(screen.getByRole('status')).toHaveTextContent(
      'Este fluxo está disponível no aplicativo Windows.',
    )
    expect(getSpy).not.toHaveBeenCalled()
    expect(
      screen.queryByRole('heading', { name: 'Backup e restauração' }),
    ).toBeInTheDocument()
  })

  it('keeps the reminder interval empty when no frequency is configured', async () => {
    const { requestSpy } = renderPage()
    const user = userEvent.setup()
    const interval = await screen.findByLabelText('Intervalo em dias')

    expect(interval).toHaveValue(null)
    await user.click(screen.getByRole('button', { name: 'Salvar lembrete' }))

    await waitFor(() =>
      expect(requestSpy).toHaveBeenCalledWith('/backups/reminder', {
        method: 'PUT',
        body: { interval_days: null },
      }),
    )
  })

  it('does not estimate storage when the folder picker is cancelled', async () => {
    const { request, spy } = makeRequest(async () => undefined)
    renderPage({ pickFolder: vi.fn().mockResolvedValue(null), request })
    const user = userEvent.setup()

    await user.click(
      screen.getByRole('button', { name: 'Selecionar HD externo' }),
    )

    expect(spy).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Pasta no HD externo')).toHaveValue('')
  })

  it('clears both backup passphrase fields after creating a backup', async () => {
    const { request, spy } = makeRequest(async (path) => {
      if (path === '/backups/estimate') return ESTIMATE
      if (path === '/backups')
        return { completed: true, reminder_updated: true }
      return undefined
    })
    renderPage({ pickFolder: vi.fn().mockResolvedValue('E:\\Backup'), request })
    const user = userEvent.setup()

    await user.click(
      screen.getByRole('button', { name: 'Selecionar HD externo' }),
    )
    const passphrase = await screen.findByLabelText(
      'Senha para proteger o backup',
    )
    const repeat = screen.getByLabelText('Repita a senha do backup')
    await user.type(passphrase, 'senha-sintetica-longa')
    await user.type(repeat, 'senha-sintetica-longa')
    await user.click(screen.getByRole('button', { name: 'Criar backup no HD' }))

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith('/backups', {
        method: 'POST',
        body: {
          destination: 'E:\\Backup',
          passphrase: 'senha-sintetica-longa',
        },
      }),
    )
    await waitFor(() => {
      expect(passphrase).toHaveValue('')
      expect(repeat).toHaveValue('')
    })
  })

  it('keeps the successful backup result when refreshing reminder status fails', async () => {
    const getSpy = vi
      .fn<(path: string) => Promise<unknown>>()
      .mockResolvedValueOnce(STATUS)
      .mockRejectedValueOnce(new Error('status refresh unavailable'))
    const get: AuthenticatedGet = async <T,>(path: string) =>
      (await getSpy(path)) as T
    const { request } = makeRequest(async (path) => {
      if (path === '/backups/estimate') return ESTIMATE
      if (path === '/backups')
        return { completed: true, reminder_updated: true }
      return undefined
    })
    const onBackupCreated = vi.fn()
    render(
      <BackupPage
        get={get}
        request={request}
        available
        onBack={vi.fn()}
        onRestored={vi.fn()}
        onBackupCreated={onBackupCreated}
        onBusyChange={vi.fn()}
        pickFolder={vi.fn().mockResolvedValue('E:\\Backup')}
      />,
    )
    const user = userEvent.setup()

    await user.click(
      screen.getByRole('button', { name: 'Selecionar HD externo' }),
    )
    const passphrase = await screen.findByLabelText(
      'Senha para proteger o backup',
    )
    const repeat = screen.getByLabelText('Repita a senha do backup')
    await user.type(passphrase, 'senha-sintetica-longa')
    await user.type(repeat, 'senha-sintetica-longa')
    await user.click(screen.getByRole('button', { name: 'Criar backup no HD' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      /Cópia criada e verificada no HD externo/,
    )
    expect(onBackupCreated).toHaveBeenCalledOnce()
    expect(passphrase).toHaveValue('')
    expect(repeat).toHaveValue('')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('requires review, both passwords, and RESTAURAR before restoring', async () => {
    const { request, spy } = makeRequest(async (path) => {
      if (path === '/backups/restore/preview') return PREVIEW
      return undefined
    })
    const { onRestored } = renderPage({
      pickFile: vi.fn().mockResolvedValue('E:\\backup.dfb'),
      request,
    })
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Selecionar backup' }))
    const backupPassword = screen.getByLabelText('Senha do backup selecionado')
    await user.type(backupPassword, 'senha-sintetica-longa')
    await user.click(
      screen.getByRole('button', { name: 'Validar e revisar backup' }),
    )
    expect(
      await screen.findByText('Confira o que será substituído'),
    ).toBeVisible()

    await user.click(
      screen.getByRole('button', { name: 'Confirmar restauração' }),
    )
    expect(spy).not.toHaveBeenCalledWith('/backups/restore', expect.anything())
    expect(onRestored).not.toHaveBeenCalled()

    await user.type(
      screen.getByLabelText('Senha de acesso ao CRM'),
      'senha-do-crm',
    )
    await user.type(
      screen.getByLabelText('Digite RESTAURAR para substituir os dados'),
      'RESTAURAR',
    )
    await user.type(
      screen.getByLabelText('Digite novamente a senha do backup'),
      'senha-sintetica-longa',
    )
    await user.click(
      screen.getByRole('button', { name: 'Confirmar restauração' }),
    )

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith('/backups/restore', {
        method: 'POST',
        body: {
          preview_token: 'preview-sintetico',
          passphrase: 'senha-sintetica-longa',
          owner_password: 'senha-do-crm',
          confirmation: 'RESTAURAR',
        },
      }),
    )
    expect(onRestored).toHaveBeenCalledOnce()
  })

  it('shows a sanitized message when a request fails', async () => {
    const request = vi
      .fn()
      .mockRejectedValue(new Error('secret path and passphrase leaked'))
    renderPage({ pickFolder: vi.fn().mockResolvedValue('E:\\Backup'), request })
    const user = userEvent.setup()

    await user.click(
      screen.getByRole('button', { name: 'Selecionar HD externo' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível concluir. Confira o HD, o espaço disponível, o arquivo e a senha do backup; depois tente novamente.',
    )
    expect(
      screen.queryByText(/secret path|passphrase leaked/),
    ).not.toBeInTheDocument()
  })
})
