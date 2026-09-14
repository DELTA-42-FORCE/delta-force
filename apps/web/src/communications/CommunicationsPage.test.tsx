import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../lib/apiClient'
import { CommunicationsPage } from './CommunicationsPage'
import type {
  MessageTemplate,
  RecipientCandidate,
  RecipientCandidateCursor,
  RecipientCandidatePage,
  RecipientDocumentStatus,
} from './communicationsApi'

const TEMPLATE_ID = '00000000-0000-0000-0000-000000000011'
const CLIENT_ID = '00000000-0000-0000-0000-000000000022'
const SECOND_CLIENT_ID = '00000000-0000-0000-0000-000000000033'

const TEMPLATE: MessageTemplate = {
  id: TEMPLATE_ID,
  name: 'Pendência documental',
  subject: 'Documentação pendente',
  body: 'Revise os documentos indicados antes de responder.',
  created_at: '2026-09-14T10:00:00Z',
  updated_at: '2026-09-14T11:00:00Z',
}

function candidate(
  id: string,
  status: RecipientDocumentStatus = 'pending',
  name = 'Ana Souza',
): RecipientCandidate {
  return {
    client_id: id,
    display_name: name,
    document_status: status,
    matching_documents: 2,
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderPage(
  overrides: {
    loadTemplates?: ReturnType<typeof vi.fn>
    createTemplate?: ReturnType<typeof vi.fn>
    updateTemplate?: ReturnType<typeof vi.fn>
    deleteTemplate?: ReturnType<typeof vi.fn>
    loadCandidates?: ReturnType<typeof vi.fn>
  } = {},
) {
  const loadTemplates =
    overrides.loadTemplates ?? vi.fn().mockResolvedValue([TEMPLATE])
  const createTemplate =
    overrides.createTemplate ?? vi.fn().mockResolvedValue(TEMPLATE)
  const updateTemplate =
    overrides.updateTemplate ?? vi.fn().mockResolvedValue(TEMPLATE)
  const deleteTemplate =
    overrides.deleteTemplate ?? vi.fn().mockResolvedValue(undefined)
  const loadCandidates =
    overrides.loadCandidates ??
    vi.fn().mockResolvedValue({
      items: [candidate(CLIENT_ID)],
      nextCursor: null,
    })

  render(
    <CommunicationsPage
      loadTemplates={loadTemplates}
      createTemplate={createTemplate}
      updateTemplate={updateTemplate}
      deleteTemplate={deleteTemplate}
      loadCandidates={loadCandidates}
      onBack={vi.fn()}
    />,
  )

  return {
    loadTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    loadCandidates,
  }
}

describe('CommunicationsPage', () => {
  it('shows saved templates and pending recipient candidates', async () => {
    const { loadCandidates } = renderPage()

    expect(await screen.findByText('Pendência documental')).toBeVisible()
    expect(await screen.findByText('Ana Souza')).toBeVisible()
    expect(screen.getByText('2 documentos nesta situação')).toBeVisible()
    expect(loadCandidates).toHaveBeenCalledWith('pending', null)
    expect(screen.getByText('Envio desativado')).toBeVisible()
  })

  it('creates a static reusable template', async () => {
    const created = { ...TEMPLATE, name: 'Aviso de documento incorreto' }
    const createTemplate = vi.fn().mockResolvedValue(created)
    const user = userEvent.setup()
    renderPage({
      loadTemplates: vi.fn().mockResolvedValue([]),
      createTemplate,
    })

    await screen.findByText('Nenhum modelo criado')
    await user.click(screen.getByRole('button', { name: 'Novo modelo' }))
    await user.type(
      screen.getByLabelText('Nome do modelo'),
      'Aviso de documento incorreto',
    )
    await user.type(screen.getByLabelText('Assunto'), 'Documento para revisar')
    await user.type(
      screen.getByLabelText('Conteúdo'),
      'Há um documento que precisa de revisão.',
    )
    await user.click(screen.getByRole('button', { name: 'Salvar modelo' }))

    await waitFor(() => expect(createTemplate).toHaveBeenCalledTimes(1))
    expect(createTemplate).toHaveBeenCalledWith({
      name: 'Aviso de documento incorreto',
      subject: 'Documento para revisar',
      body: 'Há um documento que precisa de revisão.',
    })
    expect(
      await screen.findByText('Modelo “Aviso de documento incorreto” criado.'),
    ).toBeVisible()
  })

  it('requires every template field before calling the API', async () => {
    const createTemplate = vi.fn()
    const user = userEvent.setup()
    renderPage({ createTemplate })

    await screen.findByText('Pendência documental')
    await user.click(screen.getByRole('button', { name: 'Novo modelo' }))
    await user.click(screen.getByRole('button', { name: 'Salvar modelo' }))

    expect(
      await screen.findByText(
        'Preencha o nome, o assunto e o conteúdo do modelo.',
      ),
    ).toBeVisible()
    expect(createTemplate).not.toHaveBeenCalled()
  })

  it('edits an existing template and keeps its identity', async () => {
    const updated = { ...TEMPLATE, subject: 'Novo assunto aprovado' }
    const updateTemplate = vi.fn().mockResolvedValue(updated)
    const user = userEvent.setup()
    renderPage({ updateTemplate })

    await screen.findByText('Pendência documental')
    await user.click(screen.getByRole('button', { name: 'Editar' }))
    const subject = screen.getByLabelText('Assunto')
    await user.clear(subject)
    await user.type(subject, 'Novo assunto aprovado')
    await user.click(screen.getByRole('button', { name: 'Salvar modelo' }))

    await waitFor(() => expect(updateTemplate).toHaveBeenCalledTimes(1))
    expect(updateTemplate).toHaveBeenCalledWith(TEMPLATE, {
      name: TEMPLATE.name,
      subject: 'Novo assunto aprovado',
      body: TEMPLATE.body,
    })
    expect(
      await screen.findByText('Modelo “Pendência documental” atualizado.'),
    ).toBeVisible()
  })

  it('requires inline confirmation before deleting a template', async () => {
    const deleteTemplate = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPage({ deleteTemplate })

    await screen.findByText('Pendência documental')
    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(deleteTemplate).not.toHaveBeenCalled()
    expect(screen.getByText(/Esta ação não pode ser desfeita/)).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Remover' }))

    await waitFor(() => expect(deleteTemplate).toHaveBeenCalledWith(TEMPLATE))
    expect(
      await screen.findByText('Modelo “Pendência documental” removido.'),
    ).toBeVisible()
    expect(screen.queryByText(TEMPLATE.subject)).not.toBeInTheDocument()
  })

  it('switches the document filter and loads older candidate pages', async () => {
    const cursor: RecipientCandidateCursor = {
      display_name: 'Bruno Lima',
      client_id: CLIENT_ID,
    }
    const loadCandidates = vi
      .fn()
      .mockResolvedValueOnce({
        items: [candidate(CLIENT_ID)],
        nextCursor: null,
      })
      .mockResolvedValueOnce({
        items: [candidate(CLIENT_ID, 'incorrect_incomplete', 'Bruno Lima')],
        nextCursor: cursor,
      })
      .mockResolvedValueOnce({
        items: [
          candidate(SECOND_CLIENT_ID, 'incorrect_incomplete', 'Carla Mendes'),
        ],
        nextCursor: null,
      })
    const user = userEvent.setup()
    renderPage({ loadCandidates })

    await screen.findByText('Ana Souza')
    await user.click(
      screen.getByRole('button', { name: 'Incorretos ou incompletos' }),
    )

    expect(await screen.findByText('Bruno Lima')).toBeVisible()
    expect(loadCandidates).toHaveBeenNthCalledWith(
      2,
      'incorrect_incomplete',
      null,
    )
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByText('Carla Mendes')).toBeVisible()
    expect(loadCandidates).toHaveBeenNthCalledWith(
      3,
      'incorrect_incomplete',
      cursor,
    )
  })

  it('discards an older candidate page after the document filter changes', async () => {
    const cursor: RecipientCandidateCursor = {
      display_name: 'Ana Souza',
      client_id: CLIENT_ID,
    }
    let resolveOlderPage!: (page: RecipientCandidatePage) => void
    const olderPage = new Promise<RecipientCandidatePage>((resolve) => {
      resolveOlderPage = resolve
    })
    const loadCandidates = vi
      .fn()
      .mockResolvedValueOnce({
        items: [candidate(CLIENT_ID)],
        nextCursor: cursor,
      })
      .mockReturnValueOnce(olderPage)
      .mockResolvedValueOnce({
        items: [candidate(CLIENT_ID, 'incorrect_incomplete', 'Bruno Lima')],
        nextCursor: null,
      })
    const user = userEvent.setup()
    renderPage({ loadCandidates })

    await screen.findByText('Ana Souza')
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    await user.click(
      screen.getByRole('button', { name: 'Incorretos ou incompletos' }),
    )
    expect(await screen.findByText('Bruno Lima')).toBeVisible()

    resolveOlderPage({
      items: [candidate(SECOND_CLIENT_ID, 'pending', 'Carla Mendes')],
      nextCursor: null,
    })

    await waitFor(() => expect(loadCandidates).toHaveBeenCalledTimes(3))
    expect(screen.queryByText('Carla Mendes')).not.toBeInTheDocument()
    expect(screen.getByText('Bruno Lima')).toBeVisible()
  })

  it('hides technical details from template and candidate failures', async () => {
    renderPage({
      loadTemplates: vi
        .fn()
        .mockRejectedValue(new ApiError(500, 'private database detail')),
      loadCandidates: vi
        .fn()
        .mockRejectedValue(new ApiError(500, 'private query detail')),
    })

    expect(
      await screen.findByText(
        'Não foi possível consultar os modelos agora. Tente novamente.',
      ),
    ).toBeVisible()
    expect(
      await screen.findByText(
        'Não foi possível consultar os clientes com esta situação documental agora.',
      ),
    ).toBeVisible()
    expect(screen.queryByText(/private/)).not.toBeInTheDocument()
  })
})
