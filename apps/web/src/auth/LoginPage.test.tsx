import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../lib/apiClient'
import { AuthProvider } from './AuthContext'
import { LoginPage } from './LoginPage'
import * as authApi from './authApi'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

function renderLoginPage() {
  return render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  )
}

describe('LoginPage', () => {
  it('shows an error message when the credentials are rejected', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(
      new ApiError(401, 'invalid email or password'),
    )
    const user = userEvent.setup()
    renderLoginPage()

    await user.type(screen.getByLabelText('E-mail'), 'ana@deltaforce.internal')
    await user.type(screen.getByLabelText('Senha'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(
      await screen.findByText('E-mail ou senha inválidos.'),
    ).toBeInTheDocument()
  })

  it('calls login with the typed credentials on submit', async () => {
    const loginSpy = vi.spyOn(authApi, 'login').mockResolvedValue({
      session_token: 'token-123',
      expires_at: new Date().toISOString(),
      user: {
        id: '1',
        email: 'ana@deltaforce.internal',
        full_name: 'Ana',
        is_admin: false,
      },
    })
    const user = userEvent.setup()
    renderLoginPage()

    await user.type(screen.getByLabelText('E-mail'), 'ana@deltaforce.internal')
    await user.type(screen.getByLabelText('Senha'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith(
        'ana@deltaforce.internal',
        'correct-password',
      )
    })
  })
})
