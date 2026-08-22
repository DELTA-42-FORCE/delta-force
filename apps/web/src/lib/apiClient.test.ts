import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, ApiError } from './apiClient'

function mockFetch(response: Partial<Response> & { json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    statusText: response.statusText ?? '',
    json: response.json ?? (() => Promise.resolve({})),
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('apiFetch', () => {
  it('sends bearer token only when provided', async () => {
    const fetchMock = mockFetch({})

    await apiFetch('/auth/me', { token: 'secret-token' })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.headers).toMatchObject({ Authorization: 'Bearer secret-token' })
  })

  it('throws the server detail on failure', async () => {
    mockFetch({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'invalid session' }),
    })

    await expect(apiFetch('/auth/me')).rejects.toMatchObject({
      status: 401,
      message: 'invalid session',
    } satisfies Partial<ApiError>)
  })
})
