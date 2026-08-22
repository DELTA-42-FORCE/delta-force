import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { ApiError } from '../lib/apiClient'
import * as authApi from './authApi'

async function signIn(sessionLifetimeMs = 60_000) {
  vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(false)
  vi.spyOn(authApi, 'login').mockImplementation(async () => ({
    session_token: 'raw-secret-token',
    expires_at: new Date(Date.now() + sessionLifetimeMs).toISOString(),
    user: {
      id: 'owner-id',
      email: 'proprietario@deltaforce.internal',
      full_name: 'Proprietário Delta Force',
    },
  }))

  const user = userEvent.setup()
  render(<App />)
  await user.type(
    await screen.findByLabelText('E-mail'),
    'proprietario@deltaforce.internal',
  )
  await user.type(screen.getByLabelText('Senha'), 'senha-segura-123')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(
    await screen.findByText('Olá, Proprietário Delta Force.'),
  ).toBeVisible()
  return user
}

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
      expires_at: new Date(Date.now() + 60_000).toISOString(),
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

  it('signs out after the server revokes the session', async () => {
    const logoutSpy = vi.spyOn(authApi, 'logout').mockResolvedValue()
    const user = await signIn()

    await user.click(screen.getByRole('button', { name: 'Sair' }))

    expect(
      await screen.findByRole('button', { name: 'Entrar' }),
    ).toBeInTheDocument()
    expect(logoutSpy).toHaveBeenCalledWith('raw-secret-token')
  })

  it('clears an already invalid session after logout returns 401', async () => {
    vi.spyOn(authApi, 'logout').mockRejectedValue(
      new ApiError(401, 'invalid or expired session'),
    )
    const user = await signIn()

    await user.click(screen.getByRole('button', { name: 'Sair' }))

    expect(
      await screen.findByRole('button', { name: 'Entrar' }),
    ).toBeInTheDocument()
  })

  it('hides local data before the logout request settles', async () => {
    vi.spyOn(authApi, 'logout').mockReturnValue(
      new Promise<void>(() => undefined),
    )
    const user = await signIn()

    await user.click(screen.getByRole('button', { name: 'Sair' }))

    expect(
      await screen.findByRole('button', { name: 'Entrar' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Olá, Proprietário Delta Force.'),
    ).not.toBeInTheDocument()
  })

  it.each([
    ['server error', new ApiError(500, 'internal server error')],
    ['network error', new TypeError('Failed to fetch')],
  ])('signs out locally after a %s during logout', async (_, error) => {
    vi.spyOn(authApi, 'logout').mockRejectedValue(error)
    const user = await signIn()

    await user.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Você saiu deste aplicativo, mas não foi possível confirmar o encerramento no serviço local.',
    )
    expect(
      screen.queryByText('Olá, Proprietário Delta Force.'),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('signs out locally when the server session reaches its expiry', async () => {
    await signIn(250)

    expect(
      await screen.findByRole('button', { name: 'Entrar' }, { timeout: 2_000 }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Olá, Proprietário Delta Force.'),
    ).not.toBeInTheDocument()
  })
})
