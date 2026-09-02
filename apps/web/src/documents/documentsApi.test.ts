import { describe, expect, it, vi } from 'vitest'

import {
  attachClientDocument,
  exportClientDocument,
  listClientDocuments,
} from './documentsApi'

const CLIENT_ID = '00000000-0000-0000-0000-0000000000aa'
const DOCUMENT_ID = '00000000-0000-0000-0000-000000000001'

function pdfFile() {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], 'contrato.pdf', {
    type: 'application/pdf',
  })
}

describe('listClientDocuments', () => {
  it('requests the first page without cursor parameters', async () => {
    const authenticatedGet = vi
      .fn()
      .mockResolvedValue({ items: [], next_cursor: null })

    const page = await listClientDocuments(authenticatedGet, {
      clientId: CLIENT_ID,
      limit: 20,
    })

    expect(authenticatedGet).toHaveBeenCalledWith(
      `/clients/${CLIENT_ID}/documents?limit=20`,
    )
    expect(page).toEqual({ items: [], nextCursor: null })
  })

  it('sends both cursor fields together', async () => {
    const authenticatedGet = vi
      .fn()
      .mockResolvedValue({ items: [], next_cursor: null })

    await listClientDocuments(authenticatedGet, {
      clientId: CLIENT_ID,
      limit: 10,
      cursor: { stored_at: '2026-09-01T12:00:00Z', id: DOCUMENT_ID },
    })

    const path = authenticatedGet.mock.calls[0][0] as string
    const query = new URLSearchParams(path.split('?')[1])
    expect(query.get('before_stored_at')).toBe('2026-09-01T12:00:00Z')
    expect(query.get('before_id')).toBe(DOCUMENT_ID)
  })
})

describe('attachClientDocument', () => {
  it('sends the file and only the filled annotations', async () => {
    const authenticatedUpload = vi.fn().mockResolvedValue({ id: DOCUMENT_ID })

    await attachClientDocument(authenticatedUpload, {
      clientId: CLIENT_ID,
      file: pdfFile(),
      annotations: { title: 'Contrato', category: '   ', notes: '' },
    })

    const [path, formData] = authenticatedUpload.mock.calls[0] as [
      string,
      FormData,
    ]
    expect(path).toBe(`/clients/${CLIENT_ID}/documents`)
    expect((formData.get('file') as File).name).toBe('contrato.pdf')
    expect(formData.get('title')).toBe('Contrato')
    // Anotação em branco não vira string vazia no servidor: ela some do envio.
    expect(formData.has('category')).toBe(false)
    expect(formData.has('notes')).toBe(false)
  })

  it('accepts a document without any annotation', async () => {
    const authenticatedUpload = vi.fn().mockResolvedValue({ id: DOCUMENT_ID })

    await attachClientDocument(authenticatedUpload, {
      clientId: CLIENT_ID,
      file: pdfFile(),
    })

    const [, formData] = authenticatedUpload.mock.calls[0] as [string, FormData]
    expect(formData.has('file')).toBe(true)
    expect(formData.has('title')).toBe(false)
  })
})

describe('exportClientDocument', () => {
  it('reads the copy from the authenticated content route', async () => {
    const authenticatedDownload = vi
      .fn()
      .mockResolvedValue({ blob: new Blob(['%PDF-']), filename: 'c.pdf' })

    await exportClientDocument(authenticatedDownload, {
      clientId: CLIENT_ID,
      documentId: DOCUMENT_ID,
    })

    expect(authenticatedDownload).toHaveBeenCalledWith(
      `/clients/${CLIENT_ID}/documents/${DOCUMENT_ID}/content`,
    )
  })
})
