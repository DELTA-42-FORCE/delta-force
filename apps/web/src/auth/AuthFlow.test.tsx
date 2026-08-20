import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import * as authApi from './authApi'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

describe('owner authentication flow', () => {
  it('shows first setup when there is no account', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)

    render(<App />)

    expect(
      await screen.findByRole('heading', {
        name: 'Configurar Delta Force CRM',
      }),
    ).toBeInTheDocument()
  })

  it('creates the owner, signs in, and never writes token to localStorage', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)
    const setupSpy = vi.spyOn(authApi, 'setupOwner').mockResolvedValue({
      session_token: 'raw-secret-token',
      expires_at: new Date().toISOString(),
      user: {
        id: 'owner-id',
        email: 'proprietario@deltaforce.internal',
        full_name: 'Proprietário Delta Force',
      },
    })
    const storageSpy = vi.spyOn(Storage.prototype, 'setItem')
    const user = userEvent.setup()
    render(<App />)

    await user.type(
      await screen.findByLabelText('Nome completo'),
      'Proprietário',
    )
    await user.type(
      screen.getByLabelText('E-mail'),
      'proprietario@deltaforce.internal',
    )
    await user.type(screen.getByLabelText('Senha'), 'senha-segura-123')
    await user.type(
      screen.getByLabelText('Confirmar senha'),
      'senha-segura-123',
    )
    await user.click(
      screen.getByRole('button', { name: 'Criar conta e entrar' }),
    )

    await waitFor(() => expect(setupSpy).toHaveBeenCalledOnce())
    expect(
      await screen.findByText('Olá, Proprietário Delta Force.'),
    ).toBeVisible()
    expect(storageSpy).not.toHaveBeenCalled()
  })

  it('shows login after setup has already been completed', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(false)

    render(<App />)

    expect(
      await screen.findByRole('button', { name: 'Entrar' }),
    ).toBeInTheDocument()
  })
})
