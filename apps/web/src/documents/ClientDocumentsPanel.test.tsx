import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClientFolder } from '../clients/clientsApi'
import { ApiError, type DownloadedFile } from '../lib/apiClient'
import { ClientDocumentsPanel } from './ClientDocumentsPanel'
import type {
  ClientDocument,
  ClientDocumentPage,
  DocumentCursor,
} from './documentsApi'

const FOLDER_ID = '00000000-0000-0000-0000-0000000000aa'
const FIRST_ID = '00000000-0000-0000-0000-000000000001'
const SECOND_ID = '00000000-0000-0000-0000-000000000002'

const FOLDER: ClientFolder = {
  id: FOLDER_ID,
  display_name: 'Ana Souza',
  profile_data: {},
  created_at: '2026-09-01T10:00:00Z',
  updated_at: '2026-09-01T10:00:00Z',
}

const CURSOR: DocumentCursor = {
  stored_at: '2026-09-01T12:00:00Z',
  id: FIRST_ID,
}

function documentItem(
  id: string,
  overrides: Partial<ClientDocument> = {},
): ClientDocument {
  return {
    id,
    client_folder_id: FOLDER_ID,
    original_filename: 'contrato.pdf',
    media_type: 'application/pdf',
    byte_size: 2048,
    checksum_sha256: 'a'.repeat(64),
    stored_at: '2026-09-01T12:00:00Z',
    title: null,
    category: null,
    notes: null,
    ...overrides,
  }
}

function pageOf(
  item: ClientDocument,
  nextCursor: DocumentCursor | null,
): ClientDocumentPage {
  return { items: [item], nextCursor }
}

function pdfFile(name = 'contrato.pdf') {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], name, {
    type: 'application/pdf',
  })
}

beforeEach(() => {
  // jsdom não implementa object URLs, usados pela exportação de cópia.
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderPanel(
  overrides: {
    loadPage?: (cursor: DocumentCursor | null) => Promise<ClientDocumentPage>
    attachDocument?: ReturnType<typeof vi.fn>
    exportDocument?: ReturnType<typeof vi.fn>
  } = {},
) {
  const loadPage =
    overrides.loadPage ??
    vi.fn().mockResolvedValue({ items: [], nextCursor: null })
  const attachDocument =
    overrides.attachDocument ??
    vi.fn().mockResolvedValue(documentItem(FIRST_ID))
  const exportDocument =
    overrides.exportDocument ??
    vi.fn().mockResolvedValue({
      blob: new Blob(['%PDF-']),
      filename: 'contrato.pdf',
    } satisfies DownloadedFile)

  render(
    <ClientDocumentsPanel
      folder={FOLDER}
      loadPage={loadPage}
      attachDocument={attachDocument}
      exportDocument={exportDocument}
      onBack={vi.fn()}
    />,
  )
  return { loadPage, attachDocument, exportDocument }
}

describe('ClientDocumentsPanel', () => {
  it('shows an explicit empty state for a folder without documents', async () => {
    renderPanel()

    expect(
      await screen.findByText('Nenhum documento anexado a esta pasta ainda.'),
    ).toBeVisible()
  })

  it('lists the stored documents with format and size', async () => {
    renderPanel({
      loadPage: vi.fn().mockResolvedValue(
        pageOf(
          documentItem(FIRST_ID, {
            title: 'Contrato',
            category: 'contratos',
          }),
          null,
        ),
      ),
    })

    expect(await screen.findByText('Contrato')).toBeVisible()
    expect(screen.getByText(/PDF · 2,0 KB · contratos/)).toBeVisible()
  })

  it('attaches a file with optional annotations and reloads the list', async () => {
    const attachDocument = vi.fn().mockResolvedValue(documentItem(FIRST_ID))
    const loadPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [], nextCursor: null })
      .mockResolvedValue(pageOf(documentItem(FIRST_ID), null))
    const user = userEvent.setup()
    renderPanel({ attachDocument, loadPage })

    await screen.findByText('Nenhum documento anexado a esta pasta ainda.')
    await user.upload(screen.getByLabelText('Arquivo (PDF ou JPEG)'), pdfFile())
    await user.type(screen.getByLabelText('Título (opcional)'), 'Contrato')
    await user.click(screen.getByRole('button', { name: 'Anexar documento' }))

    await waitFor(() => expect(attachDocument).toHaveBeenCalledTimes(1))
    expect(attachDocument.mock.calls[0][0].annotations).toEqual({
      title: 'Contrato',
      category: '',
      notes: '',
    })
    expect(
      await screen.findByText('"contrato.pdf" foi anexado à pasta.'),
    ).toBeVisible()
    await waitFor(() => expect(loadPage).toHaveBeenCalledTimes(2))
  })

  it('requires choosing a file before submitting', async () => {
    const attachDocument = vi.fn()
    const user = userEvent.setup()
    renderPanel({ attachDocument })

    await screen.findByText('Nenhum documento anexado a esta pasta ainda.')
    await user.click(screen.getByRole('button', { name: 'Anexar documento' }))

    expect(
      await screen.findByText('Escolha um arquivo PDF ou JPEG para anexar.'),
    ).toBeVisible()
    expect(attachDocument).not.toHaveBeenCalled()
  })

  it('explains a rejected format instead of showing the raw server error', async () => {
    const attachDocument = vi
      .fn()
      .mockRejectedValue(
        new ApiError(415, 'document content is neither a PDF nor a JPEG'),
      )
    const user = userEvent.setup()
    renderPanel({ attachDocument })

    await screen.findByText('Nenhum documento anexado a esta pasta ainda.')
    await user.upload(
      screen.getByLabelText('Arquivo (PDF ou JPEG)'),
      pdfFile('planilha.pdf'),
    )
    await user.click(screen.getByRole('button', { name: 'Anexar documento' }))

    expect(
      await screen.findByText(/o conteúdo não é um PDF ou JPEG íntegro/),
    ).toBeVisible()
  })

  it('explains that the disk is full', async () => {
    const attachDocument = vi
      .fn()
      .mockRejectedValue(new ApiError(507, 'the disk ran out of space'))
    const user = userEvent.setup()
    renderPanel({ attachDocument })

    await screen.findByText('Nenhum documento anexado a esta pasta ainda.')
    await user.upload(screen.getByLabelText('Arquivo (PDF ou JPEG)'), pdfFile())
    await user.click(screen.getByRole('button', { name: 'Anexar documento' }))

    expect(
      await screen.findByText(/Não há espaço livre suficiente/),
    ).toBeVisible()
  })

  it('exports an authorized copy of a document', async () => {
    const exportDocument = vi.fn().mockResolvedValue({
      blob: new Blob(['%PDF-']),
      filename: 'contrato assinado.pdf',
    } satisfies DownloadedFile)
    const user = userEvent.setup()
    renderPanel({
      loadPage: vi.fn().mockResolvedValue(pageOf(documentItem(FIRST_ID), null)),
      exportDocument,
    })

    await screen.findByText('contrato.pdf')
    await user.click(screen.getByRole('button', { name: 'Exportar cópia' }))

    await waitFor(() => expect(exportDocument).toHaveBeenCalledTimes(1))
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('explains an unreadable file on export', async () => {
    const user = userEvent.setup()
    renderPanel({
      loadPage: vi.fn().mockResolvedValue(pageOf(documentItem(FIRST_ID), null)),
      exportDocument: vi
        .fn()
        .mockRejectedValue(new ApiError(500, 'unreadable')),
    })

    await screen.findByText('contrato.pdf')
    await user.click(screen.getByRole('button', { name: 'Exportar cópia' }))

    expect(
      await screen.findByText(/não pôde ser lido no armazenamento local/),
    ).toBeVisible()
  })

  it('loads older documents with the stable cursor', async () => {
    const loadPage = vi
      .fn()
      .mockResolvedValueOnce(pageOf(documentItem(FIRST_ID), CURSOR))
      .mockResolvedValueOnce(
        pageOf(documentItem(SECOND_ID, { original_filename: 'rg.jpg' }), null),
      )
    const user = userEvent.setup()
    renderPanel({ loadPage })

    await screen.findByText('contrato.pdf')
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByText('rg.jpg')).toBeVisible()
    expect(screen.getByText('contrato.pdf')).toBeVisible()
    expect(loadPage).toHaveBeenNthCalledWith(1, null)
    expect(loadPage).toHaveBeenNthCalledWith(2, CURSOR)
  })

  it('offers a retry when the list cannot be loaded', async () => {
    const loadPage = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(pageOf(documentItem(FIRST_ID), null))
    const user = userEvent.setup()
    renderPanel({ loadPage })

    expect(
      await screen.findByText(
        'Não foi possível consultar os documentos desta pasta agora.',
      ),
    ).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByText('contrato.pdf')).toBeVisible()
  })
})
