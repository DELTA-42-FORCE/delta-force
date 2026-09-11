import { describe, expect, it } from 'vitest'

import { ApiError } from '../lib/apiClient'
import {
  describeImportFailure,
  describeImportOutcome,
  describeImportStatus,
  describeSummaryKey,
} from './importMessages'

describe('import labels', () => {
  it('translates preview statuses and execution outcomes', () => {
    expect(describeImportStatus('matched')).toBe('Cliente identificado')
    expect(describeImportStatus('client_ambiguous')).toContain('ambíguo')
    expect(describeImportOutcome('imported')).toBe('Importado')
    expect(describeImportOutcome('insufficient_space')).toContain('espaço')
  })

  it('labels known summary keys and echoes unknown ones', () => {
    expect(describeSummaryKey('total')).toBe('Total de arquivos')
    expect(describeSummaryKey('imported')).toBe('Importado')
    expect(describeSummaryKey('desconhecido')).toBe('desconhecido')
  })
})

describe('describeImportFailure', () => {
  it('gives a stable hint for an invalid source folder (422) without leaking the raw server detail', () => {
    const message = describeImportFailure(
      new ApiError(422, 'source path is not a directory'),
    )
    expect(message).toContain('A pasta de origem não pôde ser usada')
    expect(message).not.toContain('source path is not a directory')
  })

  it('maps insufficient space (507) to a disk-space hint', () => {
    expect(describeImportFailure(new ApiError(507, 'no space'))).toContain(
      'espaço',
    )
  })

  it('falls back to a connection message for non-API errors', () => {
    expect(describeImportFailure(new Error('offline'))).toContain(
      'serviço local',
    )
  })
})
