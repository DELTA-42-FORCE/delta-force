import { apiFetch } from '../lib/apiClient'
import type { CreateUserInput, ManagedUser } from './types'

export function listUsers(token: string): Promise<ManagedUser[]> {
  return apiFetch<ManagedUser[]>('/users', { token })
}

export function createUser(
  token: string,
  input: CreateUserInput,
): Promise<ManagedUser> {
  return apiFetch<ManagedUser>('/users', { method: 'POST', token, body: input })
}

export function setUserActive(
  token: string,
  userId: string,
  isActive: boolean,
): Promise<ManagedUser> {
  const action = isActive ? 'activate' : 'deactivate'
  return apiFetch<ManagedUser>(`/users/${userId}/${action}`, {
    method: 'POST',
    token,
  })
}
