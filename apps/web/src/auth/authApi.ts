import { apiFetch } from '../lib/apiClient'
import type { AuthenticatedUser, LoginResult, SetupOwnerInput } from './types'

export async function requiresSetup(): Promise<boolean> {
  const result = await apiFetch<{ requires_setup: boolean }>('/auth/setup')
  return result.requires_setup
}

export function setupOwner(input: SetupOwnerInput): Promise<LoginResult> {
  return apiFetch<LoginResult>('/auth/setup', { method: 'POST', body: input })
}

export function login(email: string, password: string): Promise<LoginResult> {
  return apiFetch<LoginResult>('/auth/login', {
    method: 'POST',
    body: { email, password },
  })
}

export function fetchCurrentUser(token: string): Promise<AuthenticatedUser> {
  return apiFetch<AuthenticatedUser>('/auth/me', { token })
}

export function logout(token: string): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST', token })
}
