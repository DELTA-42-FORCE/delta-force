import { describe, expect, it, vi } from 'vitest'

import {
  createMessageTemplate,
  deleteMessageTemplate,
  listMessageTemplates,
  listRecipientCandidates,
  updateMessageTemplate,
} from './communicationsApi'

const TEMPLATE_ID = '00000000-0000-0000-0000-000000000011'
const CLIENT_ID = '00000000-0000-0000-0000-000000000022'
const PAYLOAD = {
  name: 'Pendência documental',
  subject: 'Documentação pendente',
  body: 'Revise a documentação.',
}

describe('message template API', () => {
  it('lists templates through the authenticated route', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue([])

    await listMessageTemplates(authenticatedGet)

    expect(authenticatedGet).toHaveBeenCalledWith('/message-templates')
  })

  it('creates and updates a template with the complete payload', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue({ id: TEMPLATE_ID })

    await createMessageTemplate(authenticatedRequest, PAYLOAD)
    await updateMessageTemplate(authenticatedRequest, TEMPLATE_ID, PAYLOAD)

    expect(authenticatedRequest).toHaveBeenNthCalledWith(
      1,
      '/message-templates',
      { method: 'POST', body: PAYLOAD },
    )
    expect(authenticatedRequest).toHaveBeenNthCalledWith(
      2,
      `/message-templates/${TEMPLATE_ID}`,
      { method: 'PUT', body: PAYLOAD },
    )
  })

  it('deletes a template without sending a body', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue(undefined)

    await deleteMessageTemplate(authenticatedRequest, TEMPLATE_ID)

    expect(authenticatedRequest).toHaveBeenCalledWith(
      `/message-templates/${TEMPLATE_ID}`,
      { method: 'DELETE' },
    )
  })
})

describe('recipient candidate API', () => {
  it('requests the first page for a pending document status', async () => {
    const authenticatedGet = vi
      .fn()
      .mockResolvedValue({ items: [], next_cursor: null })

    const page = await listRecipientCandidates(authenticatedGet, {
      status: 'pending',
      limit: 20,
    })

    const path = authenticatedGet.mock.calls[0][0] as string
    const query = new URLSearchParams(path.split('?')[1])
    expect(path.split('?')[0]).toBe('/email-recipient-candidates')
    expect(query.get('status')).toBe('pending')
    expect(query.get('limit')).toBe('20')
    expect(query.has('before_display_name')).toBe(false)
    expect(page).toEqual({ items: [], nextCursor: null })
  })

  it('sends both stable cursor fields when loading more candidates', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue({
      items: [],
      next_cursor: null,
    })

    await listRecipientCandidates(authenticatedGet, {
      status: 'incorrect_incomplete',
      limit: 10,
      cursor: { display_name: 'Ana Souza', client_id: CLIENT_ID },
    })

    const path = authenticatedGet.mock.calls[0][0] as string
    const query = new URLSearchParams(path.split('?')[1])
    expect(query.get('status')).toBe('incorrect_incomplete')
    expect(query.get('before_display_name')).toBe('Ana Souza')
    expect(query.get('before_client_id')).toBe(CLIENT_ID)
  })
})
