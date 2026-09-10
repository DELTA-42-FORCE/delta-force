import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, type DownloadedFile } from '../lib/apiClient'
import type { ClientCursor, ClientFolder, ClientFolderPage } from './clientsApi'
import { ClientsPage } from './ClientsPage'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const pdfFile: DownloadedFile = {
  blob: new Blob(['%PDF']),
  filename: 'ficha-cadastral-ana-souza.pdf',
}

// O download real usa URL.createObjectURL, ausente no jsdom; o teste do PDF
// verifica a chamada ao caso de uso, não o salvamento em disco.
vi.mock('../lib/download', () => ({ saveDownloadedFile: vi.fn() }))

const ANA_ID = '00000000-0000-0000-0000-000000000001'
const BRUNO_ID = '00000000-0000-0000-0000-000000000002'

const CURSOR: ClientCursor = {
  display_name: 'Ana Souza',
  id: ANA_ID,
}

function folder(id: string, displayName: string): ClientFolder {
  return {
    id,
    display_name: displayName,
    profile_data: {},
    created_at: '2026-08-22T18:30:00Z',
    updated_at: '2026-08-22T18:30:00Z',
  }
}

function page(
  id: string,
  displayName: string,
  nextCursor: ClientCursor | null,
): ClientFolderPage {
  return { items: [folder(id, displayName)], nextCursor }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ClientsPage', () => {
  it('loads older pages with the stable cursor and keeps prior clients', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockResolvedValueOnce(page(ANA_ID, 'Ana Souza', CURSOR))
      .mockResolvedValueOnce(page(BRUNO_ID, 'Bruno Lima', null))
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )

    expect(await screen.findByText('Ana Souza')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByText('Bruno Lima')).toBeVisible()
    expect(screen.getByText('Ana Souza')).toBeVisible()
    expect(loadPage).toHaveBeenNthCalledWith(1, null, null)
    expect(loadPage).toHaveBeenNthCalledWith(2, CURSOR, null)
  })

  it('shows an explicit empty state', async () => {
    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={() => Promise.resolve({ items: [], nextCursor: null })}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )

    expect(
      await screen.findByText('Nenhum cliente cadastrado ainda.'),
    ).toBeVisible()
  })

  it('retries an initial failure', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockRejectedValueOnce(new Error('service unavailable'))
      .mockResolvedValueOnce({ items: [], nextCursor: null })
    const user = userEvent.setup()
    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível consultar os clientes agora.',
    )
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(2))
    expect(
      await screen.findByText('Nenhum cliente cadastrado ainda.'),
    ).toBeVisible()
  })

  it('reloads from the first page when the search query changes', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockResolvedValue({ items: [], nextCursor: null })
    const user = userEvent.setup()
    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(1))

    await user.type(screen.getByLabelText('Buscar cliente'), 'ana')
    await user.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(2))
    expect(loadPage).toHaveBeenNthCalledWith(2, null, 'ana')
  })

  it('creates a client and returns to the refreshed list', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockResolvedValue({ items: [], nextCursor: null })
    const createFolder = vi.fn().mockResolvedValue(folder(ANA_ID, 'Ana Souza'))
    const user = userEvent.setup()
    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={createFolder}
        updateFolder={vi.fn()}
      />,
    )
    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: 'Novo cliente' }))
    await user.type(screen.getByLabelText('Nome do cliente'), 'Ana Souza')
    await user.click(screen.getByRole('button', { name: 'Criar cliente' }))

    await waitFor(() =>
      expect(createFolder).toHaveBeenCalledWith({
        display_name: 'Ana Souza',
        profile_data: {},
      }),
    )
    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(2))
    expect(
      await screen.findByRole('heading', { name: 'Clientes' }),
    ).toBeVisible()
  })

  it('edits an existing client', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockResolvedValue(page(ANA_ID, 'Ana Souza', null))
    const updateFolder = vi
      .fn()
      .mockResolvedValue(folder(ANA_ID, 'Ana Souza Lima'))
    const user = userEvent.setup()
    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={updateFolder}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Editar' }))
    const nameField = screen.getByLabelText('Nome do cliente')
    await user.clear(nameField)
    await user.type(nameField, 'Ana Souza Lima')
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await waitFor(() =>
      expect(updateFolder).toHaveBeenCalledWith(ANA_ID, {
        display_name: 'Ana Souza Lima',
        profile_data: {},
      }),
    )
  })

  it('opens the documents of the chosen folder', async () => {
    const loadPage = vi
      .fn<
        (
          cursor: ClientCursor | null,
          query: string | null,
        ) => Promise<ClientFolderPage>
      >()
      .mockResolvedValue(page(ANA_ID, 'Ana Souza', null))
    const onOpenDocuments = vi.fn()
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={onOpenDocuments}
        exportProfile={vi.fn()}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Documentos' }))

    expect(onOpenDocuments).toHaveBeenCalledWith(folder(ANA_ID, 'Ana Souza'))
  })

  it('generates the profile PDF for the chosen folder', async () => {
    const loadPage = vi.fn().mockResolvedValue(page(ANA_ID, 'Ana Souza', null))
    const exportProfile = vi.fn().mockResolvedValue({
      blob: new Blob(['%PDF']),
      filename: 'ficha-cadastral-ana-souza.pdf',
    })
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={exportProfile}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Ficha PDF' }))

    await waitFor(() =>
      expect(exportProfile).toHaveBeenCalledWith(folder(ANA_ID, 'Ana Souza')),
    )
  })

  it('blocks a second generation while one is pending and re-enables after it settles', async () => {
    const loadPage = vi.fn().mockResolvedValue({
      items: [folder(ANA_ID, 'Ana Souza'), folder(BRUNO_ID, 'Bruno Lima')],
      nextCursor: null,
    })
    const ana = deferred<DownloadedFile>()
    const exportProfile = vi.fn().mockReturnValueOnce(ana.promise)
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={exportProfile}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    const [anaButton, brunoButton] = screen.getAllByRole('button', {
      name: 'Ficha PDF',
    })
    await user.click(anaButton)

    // Enquanto a ficha de Ana está pendente, todos os botões ficam inativos.
    expect(
      await screen.findByRole('button', { name: 'Gerando…' }),
    ).toBeDisabled()
    expect(brunoButton).toBeDisabled()

    // Clicar em Bruno não dispara uma segunda geração concorrente.
    await user.click(brunoButton)
    expect(exportProfile).toHaveBeenCalledTimes(1)
    expect(exportProfile).toHaveBeenCalledWith(folder(ANA_ID, 'Ana Souza'))

    // Concluída a operação, os botões voltam a ficar habilitados.
    ana.resolve(pdfFile)
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: 'Ficha PDF' })).toHaveLength(
        2,
      ),
    )
    for (const button of screen.getAllByRole('button', { name: 'Ficha PDF' })) {
      expect(button).toBeEnabled()
    }
  })

  it('ignores a double click on the same generate button', async () => {
    const loadPage = vi.fn().mockResolvedValue(page(ANA_ID, 'Ana Souza', null))
    const pending = deferred<DownloadedFile>()
    const exportProfile = vi.fn().mockReturnValue(pending.promise)
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={exportProfile}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.dblClick(screen.getByRole('button', { name: 'Ficha PDF' }))

    expect(exportProfile).toHaveBeenCalledTimes(1)
    pending.resolve(pdfFile)
  })

  it('shows an alert when the profile PDF cannot be generated', async () => {
    const loadPage = vi.fn().mockResolvedValue(page(ANA_ID, 'Ana Souza', null))
    const exportProfile = vi.fn().mockRejectedValue(new ApiError(404, 'gone'))
    const user = userEvent.setup()

    render(
      <ClientsPage
        onOpenDocuments={vi.fn()}
        exportProfile={exportProfile}
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Ficha PDF' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'não existe mais',
    )
  })
})
