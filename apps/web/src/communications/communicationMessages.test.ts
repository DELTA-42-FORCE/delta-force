import { describe, expect, it } from 'vitest'

import { ApiError } from '../lib/apiClient'
import {
  describeCandidateFailure,
  describeTemplateFailure,
} from './communicationMessages'

describe('describeTemplateFailure', () => {
  it('does not expose a technical backend error', () => {
    const message = describeTemplateFailure(
      new ApiError(500, 'database connection leaked'),
      'save',
    )

    expect(message).toMatch(/Nada foi alterado/)
    expect(message).not.toContain('database connection leaked')
  })

  it('explains validation and stale template failures', () => {
    expect(describeTemplateFailure(new ApiError(422, 'raw'), 'save')).toMatch(
      /Revise o nome, o assunto e o conteúdo/,
    )
    expect(describeTemplateFailure(new ApiError(404, 'raw'), 'delete')).toMatch(
      /não existe mais/,
    )
  })
})

describe('describeCandidateFailure', () => {
  it('uses a safe message for a failed query', () => {
    const message = describeCandidateFailure(
      new ApiError(500, 'private query detail'),
    )

    expect(message).toMatch(/situação documental/)
    expect(message).not.toContain('private query detail')
  })
})
