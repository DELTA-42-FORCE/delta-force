import { apiFetch } from '../lib/apiClient'
import type { AuthenticatedUser, LoginResult } from './types'

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
