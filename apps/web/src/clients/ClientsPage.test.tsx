import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ClientCursor, ClientFolder, ClientFolderPage } from './clientsApi'
import { ClientsPage } from './ClientsPage'

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
        loadPage={loadPage}
        createFolder={vi.fn()}
        updateFolder={vi.fn()}
      />,
    )
    expect(await screen.findByText('Ana Souza')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Documentos' }))

    expect(onOpenDocuments).toHaveBeenCalledWith(folder(ANA_ID, 'Ana Souza'))
  })
})
