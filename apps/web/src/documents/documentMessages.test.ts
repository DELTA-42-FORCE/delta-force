import { describe, expect, it } from 'vitest'

import { ApiError } from '../lib/apiClient'
import {
  describeAttachFailure,
  describeExportFailure,
  describeMediaType,
  formatByteSize,
} from './documentMessages'

describe('describeAttachFailure', () => {
  it.each([
    [415, /não é um PDF ou JPEG íntegro/],
    [507, /Não há espaço livre suficiente/],
    [404, /pasta de cliente não existe mais/],
    [403, /acesso a esta pasta foi negado/],
    [401, /sessão expirou/i],
    [500, /Falha ao gravar o documento/],
  ])('explains status %i in plain language', (status, expected) => {
    expect(describeAttachFailure(new ApiError(status, 'raw detail'))).toMatch(
      expected,
    )
  })

  it('keeps the server detail on 422 because it names the invalid field', () => {
    const message = describeAttachFailure(
      new ApiError(422, 'document filename must be a .pdf, .jpg or .jpeg'),
    )

    expect(message).toContain('document filename must be a .pdf, .jpg or .jpeg')
  })

  it('reports a transport failure when the service is unreachable', () => {
    expect(describeAttachFailure(new TypeError('failed to fetch'))).toMatch(
      /serviço local do CRM/,
    )
  })
})

describe('describeExportFailure', () => {
  it('explains an unreadable file', () => {
    expect(describeExportFailure(new ApiError(500, 'unreadable'))).toMatch(
      /não pôde ser lido no armazenamento local/,
    )
  })

  it('explains a document missing from the folder', () => {
    expect(describeExportFailure(new ApiError(404, 'not found'))).toMatch(
      /Documento não encontrado nesta pasta/,
    )
  })
})

describe('formatByteSize', () => {
  it.each([
    [0, '0 B'],
    [512, '512 B'],
    [2048, '2,0 KB'],
    [5 * 1024 * 1024, '5,0 MB'],
  ])('formats %i bytes as %s', (bytes, expected) => {
    expect(formatByteSize(bytes)).toBe(expected)
  })

  it('does not invent a size for an invalid value', () => {
    expect(formatByteSize(Number.NaN)).toBe('—')
  })
})

describe('describeMediaType', () => {
  it('uses short labels for the accepted formats', () => {
    expect(describeMediaType('application/pdf')).toBe('PDF')
    expect(describeMediaType('image/jpeg')).toBe('JPEG')
  })
})
