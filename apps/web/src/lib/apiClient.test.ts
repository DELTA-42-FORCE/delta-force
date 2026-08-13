import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, ApiError } from './apiClient'

function mockFetchOnce(response: Partial<Response> & { json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    statusText: response.statusText ?? '',
    json: response.json ?? (() => Promise.resolve({})),
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('returns the parsed JSON body on success', async () => {
    mockFetchOnce({ ok: true, json: () => Promise.resolve({ hello: 'world' }) })

    const result = await apiFetch<{ hello: string }>('/ping')

    expect(result).toEqual({ hello: 'world' })
  })

  it('sends the bearer token and JSON body when provided', async () => {
    const fetchMock = mockFetchOnce({ ok: true })

    await apiFetch('/auth/login', {
      method: 'POST',
      token: 'abc123',
      body: { email: 'a@b.com' },
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({
      Authorization: 'Bearer abc123',
      'Content-Type': 'application/json',
    })
    expect(init.body).toBe(JSON.stringify({ email: 'a@b.com' }))
  })

  it('throws ApiError with the server detail on failure', async () => {
    mockFetchOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'invalid email or password' }),
    })

    await expect(apiFetch('/auth/login')).rejects.toMatchObject({
      status: 401,
      message: 'invalid email or password',
    } satisfies Partial<ApiError>)
  })

  it('returns undefined for a 204 No Content response', async () => {
    mockFetchOnce({ ok: true, status: 204 })

    const result = await apiFetch<void>('/auth/logout', { method: 'POST' })

    expect(result).toBeUndefined()
  })
})
