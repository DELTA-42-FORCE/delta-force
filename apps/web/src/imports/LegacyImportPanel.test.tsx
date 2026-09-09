import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../lib/apiClient'
import { LegacyImportPanel } from './LegacyImportPanel'
import type { LegacyImportPreview, LegacyImportResult } from './importsApi'

afterEach(cleanup)

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
    expect(alert).toHaveTextContent('source path is not a directory')
    expect(importButton()).not.toBeInTheDocument()
  })
})
