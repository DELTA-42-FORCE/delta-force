import { describe, expect, it, vi } from 'vitest'

import {
  createClientFolder,
  getClientFolder,
  listClientFolders,
  updateClientFolder,
} from './clientsApi'

describe('listClientFolders', () => {
  it('requests a bounded page without extra params by default', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue({
      items: [],
      next_cursor: null,
    })

    await listClientFolders(authenticatedGet, { limit: 20 })

    expect(authenticatedGet).toHaveBeenCalledWith('/clients?limit=20')
  })

  it('encodes the query and cursor when loading an older, filtered page', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue({
      items: [],
      next_cursor: null,
    })

    await listClientFolders(authenticatedGet, {
      limit: 20,
      query: 'ana',
      cursor: {
        display_name: 'Ana Souza',
        id: '00000000-0000-0000-0000-000000000001',
      },
    })

    expect(authenticatedGet).toHaveBeenCalledWith(
      '/clients?limit=20&query=ana&before_display_name=Ana+Souza&before_id=00000000-0000-0000-0000-000000000001',
    )
  })
})

describe('getClientFolder', () => {
  it('requests a single client by id', async () => {
    const client = {
      id: '00000000-0000-0000-0000-000000000001',
      display_name: 'Ana Souza',
      profile_data: {},
      created_at: '2026-08-22T18:30:00Z',
      updated_at: '2026-08-22T18:30:00Z',
    }
    const authenticatedGet = vi.fn().mockResolvedValue(client)

    await expect(
      getClientFolder(authenticatedGet, '00000000-0000-0000-0000-000000000001'),
    ).resolves.toEqual(client)
    expect(authenticatedGet).toHaveBeenCalledWith(
      '/clients/00000000-0000-0000-0000-000000000001',
    )
  })
})

describe('createClientFolder', () => {
  it('posts the display name and optional profile data', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue({})

    await createClientFolder(authenticatedRequest, {
      display_name: 'Ana Souza',
      profile_data: { telefone: '123' },
    })

    expect(authenticatedRequest).toHaveBeenCalledWith('/clients', {
      method: 'POST',
      body: { display_name: 'Ana Souza', profile_data: { telefone: '123' } },
    })
  })
})

describe('updateClientFolder', () => {
  it('sends a PUT with the updated fields', async () => {
    const authenticatedRequest = vi.fn().mockResolvedValue({})

    await updateClientFolder(
      authenticatedRequest,
      '00000000-0000-0000-0000-000000000001',
      {
        display_name: 'Ana Souza Lima',
        profile_data: {},
      },
    )

    expect(authenticatedRequest).toHaveBeenCalledWith(
      '/clients/00000000-0000-0000-0000-000000000001',
      {
        method: 'PUT',
        body: { display_name: 'Ana Souza Lima', profile_data: {} },
      },
    )
  })
})
