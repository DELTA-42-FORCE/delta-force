import { describe, expect, it } from 'vitest'

import { ApiError } from '../lib/apiClient'
import { describeProfileExportFailure } from './clientMessages'

describe('describeProfileExportFailure', () => {
  it('maps an expired session (401)', () => {
    expect(
      describeProfileExportFailure(new ApiError(401, 'expired')),
    ).toContain('sessão expirou')
  })

  it('maps a missing folder (404)', () => {
    expect(
      describeProfileExportFailure(new ApiError(404, 'not found')),
    ).toContain('não existe mais')
  })

  it('uses a generic message for other API failures', () => {
    expect(describeProfileExportFailure(new ApiError(500, 'boom'))).toContain(
      'Não foi possível gerar a ficha',
    )
  })

  it('falls back to a connection message for non-API errors', () => {
    expect(describeProfileExportFailure(new Error('offline'))).toContain(
      'serviço local',
    )
  })
})
