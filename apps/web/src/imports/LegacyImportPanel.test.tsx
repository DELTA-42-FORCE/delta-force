import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../lib/apiClient'
import { LegacyImportPanel } from './LegacyImportPanel'
import type { LegacyImportPreview, LegacyImportResult } from './importsApi'

afterEach(cleanup)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const SOURCE = 'C:\\Clientes'

const PREVIEW: LegacyImportPreview = {
  source_path: SOURCE,
  summary: {
    matched: 1,
    client_not_found: 1,
    client_ambiguous: 0,
    unsupported_format: 0,
    unreadable: 1,
    total: 3,
  },
  items: [
    {
      relative_path: 'Ana Souza/contrato.pdf',
      client_folder_name: 'Ana Souza',
      status: 'matched',
      media_type: 'application/pdf',
      matched_client_id: '00000000-0000-0000-0000-0000000000aa',
    },
    {
      relative_path: 'Fulano/rg.jpg',
      client_folder_name: 'Fulano',
      status: 'client_not_found',
      media_type: 'image/jpeg',
      matched_client_id: null,
    },
    {
      relative_path: 'quebrado.pdf',
      client_folder_name: null,
      status: 'unreadable',
      media_type: null,
      matched_client_id: null,
    },
  ],
}

const RESULT: LegacyImportResult = {
  source_path: SOURCE,
  summary: {
    imported: 1,
    duplicate: 0,
    skipped: 2,
    unsupported_format: 0,
    unreadable: 0,
    insufficient_space: 0,
    failed: 0,
    total: 3,
  },
  items: [
    {
      relative_path: 'Ana Souza/contrato.pdf',
      client_folder_name: 'Ana Souza',
      outcome: 'imported',
      document_id: '00000000-0000-0000-0000-000000000001',
    },
  ],
}

function importButton() {
  return screen.queryByRole('button', { name: 'Importar acervo' })
}

async function fillAndPreview(
  previewImport = vi.fn().mockResolvedValue(PREVIEW),
) {
  const runImport = vi.fn().mockResolvedValue(RESULT)
  const onBack = vi.fn()
  render(
    <LegacyImportPanel
      previewImport={previewImport}
      runImport={runImport}
      onBack={onBack}
    />,
  )
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Pasta de origem'), SOURCE)
  await user.click(screen.getByRole('button', { name: 'Pré-visualizar' }))
  return { user, previewImport, runImport, onBack }
}

describe('LegacyImportPanel', () => {
  it('runs a dry-run preview and lists each file with its status', async () => {
    const { previewImport } = await fillAndPreview()

    await screen.findByText('Prévia — nada foi importado ainda')
    expect(previewImport).toHaveBeenCalledWith(SOURCE)
    const rows = within(screen.getByRole('table'))
    expect(rows.getByText('Ana Souza/contrato.pdf')).toBeInTheDocument()
    expect(rows.getByText('Cliente identificado')).toBeInTheDocument()
    expect(rows.getByText('quebrado.pdf')).toBeInTheDocument()
  })

  it('gates the import behind a preview of the same folder', async () => {
    render(
      <LegacyImportPanel
        previewImport={vi.fn().mockResolvedValue(PREVIEW)}
        runImport={vi.fn().mockResolvedValue(RESULT)}
        onBack={vi.fn()}
      />,
    )
    // Sem prévia, não há botão de importar.
    expect(importButton()).not.toBeInTheDocument()
  })

  it('clears the review when the source path is edited', async () => {
    const { user } = await fillAndPreview()
    await screen.findByText('Prévia — nada foi importado ainda')
    expect(importButton()).toBeInTheDocument()

    await user.type(screen.getByLabelText('Pasta de origem'), '\\Outra')

    expect(importButton()).not.toBeInTheDocument()
    expect(
      screen.queryByText('Prévia — nada foi importado ainda'),
    ).not.toBeInTheDocument()
  })

  it('imports after review and shows the outcome report', async () => {
    const { user, runImport } = await fillAndPreview()
    await screen.findByText('Prévia — nada foi importado ainda')

    await user.click(screen.getByRole('button', { name: 'Importar acervo' }))

    await screen.findByText('Importação concluída')
    expect(runImport).toHaveBeenCalledWith(SOURCE)
    expect(
      within(screen.getByRole('table')).getByText('Importado'),
    ).toBeInTheDocument()
  })

  it('disables the import when no file has a matched client', async () => {
    const noMatch: LegacyImportPreview = {
      ...PREVIEW,
      summary: { ...PREVIEW.summary, matched: 0 },
      items: [PREVIEW.items[1]],
    }
    await fillAndPreview(vi.fn().mockResolvedValue(noMatch))
    await screen.findByText('Prévia — nada foi importado ainda')

    expect(importButton()).toBeDisabled()
  })

  it('shows an actionable error when the source folder is invalid', async () => {
    await fillAndPreview(
      vi
        .fn()
        .mockRejectedValue(new ApiError(422, 'source path is not a directory')),
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('A pasta de origem não pôde ser usada')
    expect(alert).not.toHaveTextContent('source path is not a directory')
    expect(importButton()).not.toBeInTheDocument()
  })

  it('locks the field while a preview runs and confirms the folder the preview analyzed', async () => {
    const preview = deferred<LegacyImportPreview>()
    // O servidor normaliza o caminho; a confirmação deve seguir o que a prévia
    // devolveu, não o texto digitado.
    const analyzed: LegacyImportPreview = {
      ...PREVIEW,
      source_path: 'C:\\Clientes\\Normalizado',
    }
    const previewImport = vi.fn().mockReturnValue(preview.promise)
    const runImport = vi.fn().mockResolvedValue(RESULT)
    render(
      <LegacyImportPanel
        previewImport={previewImport}
        runImport={runImport}
        onBack={vi.fn()}
      />,
    )
    const user = userEvent.setup()
    const field = screen.getByLabelText('Pasta de origem')
    await user.type(field, SOURCE)
    await user.click(screen.getByRole('button', { name: 'Pré-visualizar' }))

    // Durante a prévia o campo e a navegação ficam travados: a pasta não muda.
    expect(field).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled()
    await user.type(field, '\\Outra')
    expect(field).toHaveValue(SOURCE)

    preview.resolve(analyzed)
    await screen.findByText('Prévia — nada foi importado ainda')
    await user.click(screen.getByRole('button', { name: 'Importar acervo' }))

    await screen.findByText('Importação concluída')
    expect(runImport).toHaveBeenCalledWith('C:\\Clientes\\Normalizado')
    expect(runImport).not.toHaveBeenCalledWith(SOURCE)
  })

  it('fills the source from the native folder picker in the desktop shell', async () => {
    const pickFolder = vi.fn().mockResolvedValue('D:\\Acervo\\Legado')
    const previewImport = vi.fn().mockResolvedValue({
      ...PREVIEW,
      source_path: 'D:\\Acervo\\Legado',
    })
    render(
      <LegacyImportPanel
        previewImport={previewImport}
        runImport={vi.fn().mockResolvedValue(RESULT)}
        onBack={vi.fn()}
        pickFolder={pickFolder}
      />,
    )
    const user = userEvent.setup()

    // No shell o campo não é digitável: a pasta vem do seletor nativo.
    const field = screen.getByLabelText('Pasta de origem')
    expect(field).toHaveAttribute('readonly')

    await user.click(screen.getByRole('button', { name: 'Escolher pasta…' }))
    expect(field).toHaveValue('D:\\Acervo\\Legado')

    await user.click(screen.getByRole('button', { name: 'Pré-visualizar' }))
    await screen.findByText('Prévia — nada foi importado ainda')
    expect(previewImport).toHaveBeenCalledWith('D:\\Acervo\\Legado')
  })

  it('has no native picker and keeps the field editable in the browser', async () => {
    render(
      <LegacyImportPanel
        previewImport={vi.fn().mockResolvedValue(PREVIEW)}
        runImport={vi.fn().mockResolvedValue(RESULT)}
        onBack={vi.fn()}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Escolher pasta…' }),
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText('Pasta de origem')).not.toHaveAttribute(
      'readonly',
    )
  })

  it('locks the field while the import runs', async () => {
    const run = deferred<LegacyImportResult>()
    const runImport = vi.fn().mockReturnValue(run.promise)
    render(
      <LegacyImportPanel
        previewImport={vi.fn().mockResolvedValue(PREVIEW)}
        runImport={runImport}
        onBack={vi.fn()}
      />,
    )
    const user = userEvent.setup()
    const field = screen.getByLabelText('Pasta de origem')
    await user.type(field, SOURCE)
    await user.click(screen.getByRole('button', { name: 'Pré-visualizar' }))
    await screen.findByText('Prévia — nada foi importado ainda')

    await user.click(screen.getByRole('button', { name: 'Importar acervo' }))

    // Enquanto a importação corre, o campo e a navegação seguem travados.
    expect(field).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled()

    run.resolve(RESULT)
    await screen.findByText('Importação concluída')
  })
})
