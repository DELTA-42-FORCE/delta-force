import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthContext'
import * as authApi from '../auth/authApi'
import * as usersApi from './usersApi'
import { UsersPage } from './UsersPage'
import type { ManagedUser } from './types'

const ADMIN_USER = {
  id: 'admin-1',
  email: 'admin@deltaforce.internal',
  full_name: 'Admin',
  is_admin: true,
}

function signInAsAdmin() {
  window.localStorage.setItem('delta-force:session-token', 'admin-token')
  vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(ADMIN_USER)
}

async function renderUsersPage() {
  const view = render(
    <AuthProvider>
      <UsersPage />
    </AuthProvider>,
  )
  await waitFor(() => expect(authApi.fetchCurrentUser).toHaveBeenCalled())
  return view
}

beforeEach(() => {
  signInAsAdmin()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

describe('UsersPage', () => {
  it('shows the empty state when there are no users yet', async () => {
    vi.spyOn(usersApi, 'listUsers').mockResolvedValue([])

    await renderUsersPage()

    expect(
      await screen.findByText('Nenhum usuário cadastrado ainda.'),
    ).toBeInTheDocument()
  })

  it('lists the users returned by the API', async () => {
    const users: ManagedUser[] = [
      {
        id: 'u1',
        email: 'user@deltaforce.internal',
        full_name: 'Usuário Um',
        is_active: true,
        is_admin: false,
      },
    ]
    vi.spyOn(usersApi, 'listUsers').mockResolvedValue(users)

    await renderUsersPage()

    expect(await screen.findByText('Usuário Um')).toBeInTheDocument()
    expect(screen.getByText('Ativo')).toBeInTheDocument()
  })

  it('creates a user through the form', async () => {
    vi.spyOn(usersApi, 'listUsers').mockResolvedValue([])
    const createSpy = vi.spyOn(usersApi, 'createUser').mockResolvedValue({
      id: 'u2',
      email: 'nova@deltaforce.internal',
      full_name: 'Nova Conta',
      is_active: true,
      is_admin: false,
    })
    const user = userEvent.setup()
    await renderUsersPage()

    await user.type(screen.getByLabelText('Nome'), 'Nova Conta')
    await user.type(screen.getByLabelText('E-mail'), 'nova@deltaforce.internal')
    await user.type(
      screen.getByLabelText('Senha provisória'),
      'senha-forte-123',
    )
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('admin-token', {
        email: 'nova@deltaforce.internal',
        full_name: 'Nova Conta',
        password: 'senha-forte-123',
        is_admin: false,
      })
    })
  })
})
