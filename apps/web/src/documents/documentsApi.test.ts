import { describe, expect, it, vi } from 'vitest'

import {
  attachClientDocument,
  exportClientDocument,
  listClientDocuments,
  openClientDocument,
  updateClientDocumentStatus,
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

    const [path, file, headers] = authenticatedUpload.mock.calls[0] as [
      string,
      File,
      Record<string, string>,
    ]
    expect(path).toBe(`/clients/${CLIENT_ID}/documents`)
    expect(file.name).toBe('contrato.pdf')
    expect(headers['X-Delta-Document-Filename']).toBe('contrato.pdf')
    expect(headers['X-Delta-Document-Title']).toBe('Contrato')
    // Anotação em branco não vira header vazio no servidor: ela some do envio.
    expect(headers).not.toHaveProperty('X-Delta-Document-Category')
    expect(headers).not.toHaveProperty('X-Delta-Document-Notes')
  })

  it('accepts a document without any annotation', async () => {
    const authenticatedUpload = vi.fn().mockResolvedValue({ id: DOCUMENT_ID })

    await attachClientDocument(authenticatedUpload, {
      clientId: CLIENT_ID,
      file: pdfFile(),
    })

    const [, file, headers] = authenticatedUpload.mock.calls[0] as [
      string,
      File,
      Record<string, string>,
    ]
    expect(file.name).toBe('contrato.pdf')
    expect(headers).toEqual({
      'X-Delta-Document-Filename': 'contrato.pdf',
    })
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

describe('updateClientDocumentStatus', () => {
  it('patches the optional tracking status', async () => {
    const authenticatedRequest = vi
      .fn()
      .mockResolvedValue({ id: DOCUMENT_ID, status: 'pending' })

    await updateClientDocumentStatus(authenticatedRequest, {
      clientId: CLIENT_ID,
      documentId: DOCUMENT_ID,
      status: 'pending',
    })

    expect(authenticatedRequest).toHaveBeenCalledWith(
      `/clients/${CLIENT_ID}/documents/${DOCUMENT_ID}/status`,
      { method: 'PATCH', body: { status: 'pending' } },
    )
  })

  it('sends null to remove tracking', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue({
      id: DOCUMENT_ID,
      status: null,
    })

    await updateClientDocumentStatus(authenticatedRequest, {
      clientId: CLIENT_ID,
      documentId: DOCUMENT_ID,
      status: null,
    })

    expect(authenticatedRequest).toHaveBeenCalledWith(expect.any(String), {
      method: 'PATCH',
      body: { status: null },
    })
  })
})

describe('openClientDocument', () => {
  it('delegates the document identity without materializing a download', async () => {
    const authenticatedOpenDocument = vi.fn().mockResolvedValue('desktop-app')

    await openClientDocument(authenticatedOpenDocument, {
      clientId: CLIENT_ID,
      documentId: DOCUMENT_ID,
      filename: 'contrato.pdf',
    })

    expect(authenticatedOpenDocument).toHaveBeenCalledWith({
      path: `/clients/${CLIENT_ID}/documents/${DOCUMENT_ID}/content`,
      clientId: CLIENT_ID,
      documentId: DOCUMENT_ID,
      filename: 'contrato.pdf',
    })
  })
})
