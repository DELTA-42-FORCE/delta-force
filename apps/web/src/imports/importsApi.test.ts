import { describe, expect, it, vi } from 'vitest'

import { importLegacyArchive, previewLegacyImport } from './importsApi'

const SOURCE = 'C:\\Clientes'
const EMPTY = { source_path: SOURCE, summary: { total: 0 }, items: [] }

describe('previewLegacyImport', () => {
  it('posts the source path to the dry-run endpoint', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue(EMPTY)

    const preview = await previewLegacyImport(authenticatedRequest, SOURCE)

    expect(authenticatedRequest).toHaveBeenCalledWith(
      '/imports/legacy/preview',
      {
        method: 'POST',
        body: { source_path: SOURCE },
      },
    )
    expect(preview.items).toEqual([])
  })
})

describe('importLegacyArchive', () => {
  it('posts the source path to the execute endpoint', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue(EMPTY)

    await importLegacyArchive(authenticatedRequest, SOURCE)

    expect(authenticatedRequest).toHaveBeenCalledWith('/imports/legacy', {
      method: 'POST',
      body: { source_path: SOURCE },
    })
  })
})
