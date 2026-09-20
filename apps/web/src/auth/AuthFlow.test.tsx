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
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], limit: 5, next_cursor: null }),
    }),
  )

  const user = userEvent.setup()
  render(<App />)
  await user.type(
    await screen.findByLabelText('E-mail'),
    'proprietario@deltaforce.internal',
  )
  await user.type(screen.getByLabelText('Senha'), 'senha-segura-123')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(
    await screen.findByRole('heading', {
      name: 'Bem-vindo, Proprietário Delta Force',
    }),
  ).toBeVisible()
  return user
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('owner authentication flow', () => {
  it('shows first setup when there is no account', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)

    render(<App />)

    expect(
      await screen.findByRole('heading', {
        name: 'Configure sua conta',
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
      await screen.findByRole('heading', {
        name: 'Bem-vindo, Proprietário Delta Force',
      }),
    ).toBeVisible()
    expect(
      screen.getByText(
        'Clientes, documentos, contratos e modelos já estão disponíveis. O envio de e-mails aguarda a configuração segura do remetente.',
      ),
    ).toBeVisible()
    expect(
      screen.queryByText(/a próxima etapa adicionará/i),
    ).not.toBeInTheDocument()
    expect(storageSpy).not.toHaveBeenCalled()
  })

  it('explains how to correct setup data rejected by validation', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)
    vi.spyOn(authApi, 'setupOwner').mockRejectedValue(
      new ApiError(422, 'technical validation detail'),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.type(
      await screen.findByLabelText('Nome completo'),
      'Proprietário',
    )
    await user.type(screen.getByLabelText('E-mail'), 'teste@example.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-segura-123')
    await user.type(
      screen.getByLabelText('Confirmar senha'),
      'senha-segura-123',
    )
    await user.click(
      screen.getByRole('button', { name: 'Criar conta e entrar' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Revise os campos indicados. O nome deve ter entre 2 e 200 caracteres; use um e-mail válido e uma senha de 12 a 72 caracteres, com no máximo 72 bytes.',
    )
    expect(screen.getByRole('alert')).not.toHaveTextContent(
      'technical validation detail',
    )
    expect(screen.getByLabelText('Nome completo')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(screen.getByLabelText('E-mail')).toHaveAttribute(
      'aria-describedby',
      'setup-validation-error',
    )
  })

  it('validates email and UTF-8 password size before calling the API', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)
    const setupSpy = vi.spyOn(authApi, 'setupOwner')
    const user = userEvent.setup()
    render(<App />)

    await user.type(await screen.findByLabelText('Nome completo'), 'Dono local')
    await user.type(screen.getByLabelText('E-mail'), 'email-invalido')
    await user.type(screen.getByLabelText('Senha'), 'á'.repeat(40))
    await user.type(screen.getByLabelText('Confirmar senha'), 'á'.repeat(40))

    const submitButton = screen.getByRole('button', {
      name: 'Criar conta e entrar',
    })
    expect(submitButton.closest('form')).toHaveAttribute('novalidate')
    await user.click(submitButton)

    expect(setupSpy).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /senha de 12 a 72 caracteres, com no máximo 72 bytes/,
    )
    expect(screen.getByLabelText('E-mail')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(screen.getByLabelText('Senha')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(screen.getByLabelText('E-mail')).toHaveFocus()
  })

  it('keeps unrelated field errors while the owner corrects one field', async () => {
    vi.spyOn(authApi, 'requiresSetup').mockResolvedValue(true)
    const setupSpy = vi.spyOn(authApi, 'setupOwner')
    const user = userEvent.setup()
    render(<App />)

    const fullNameInput = await screen.findByLabelText('Nome completo')
    const emailInput = screen.getByLabelText('E-mail')
    const passwordInput = screen.getByLabelText('Senha')

    await user.click(
      screen.getByRole('button', { name: 'Criar conta e entrar' }),
    )

    expect(setupSpy).not.toHaveBeenCalled()
    expect(fullNameInput).toHaveFocus()
    expect(fullNameInput).toHaveAttribute('aria-invalid', 'true')
    expect(emailInput).toHaveAttribute('aria-invalid', 'true')
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true')

    await user.type(fullNameInput, 'Dono local')

    expect(fullNameInput).not.toHaveAttribute('aria-invalid')
    expect(emailInput).toHaveAttribute('aria-invalid', 'true')
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Revise os campos indicados.',
    )

    await user.type(emailInput, 'dono@example.com')
    await user.type(passwordInput, 'senha-segura-123')

    const confirmationInput = screen.getByLabelText('Confirmar senha')
    expect(confirmationInput).toHaveAttribute('aria-invalid', 'true')

    await user.type(confirmationInput, 'senha-segura-123')

    expect(confirmationInput).not.toHaveAttribute('aria-invalid')
    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    await user.clear(emailInput)

    expect(emailInput).toHaveAttribute('aria-invalid', 'true')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Revise os campos indicados.',
    )
    expect(emailInput).toHaveAttribute(
      'aria-describedby',
      'setup-validation-error',
    )
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

  it('loads recent activity with the in-memory session token', async () => {
    await signIn()

    await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/audit/events?limit=5',
      expect.objectContaining({
        headers: { Authorization: 'Bearer raw-secret-token' },
      }),
    )
  })

  it('opens the complete authenticated audit history from the menu', async () => {
    const user = await signIn()
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce())

    await user.click(screen.getByRole('button', { name: 'Auditoria' }))

    expect(
      await screen.findByRole('heading', { name: 'Histórico de auditoria' }),
    ).toBeVisible()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(fetch).toHaveBeenLastCalledWith(
      'http://localhost:8000/audit/events?limit=20',
      expect.objectContaining({
        headers: { Authorization: 'Bearer raw-secret-token' },
      }),
    )

    await user.click(
      screen.getByRole('button', { name: '← Voltar para visão geral' }),
    )
    expect(
      await screen.findByRole('heading', {
        name: 'Bem-vindo, Proprietário Delta Force',
      }),
    ).toBeVisible()
  })

  it('opens email preparation with authenticated template and triage requests', async () => {
    const user = await signIn()
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      const body = url.endsWith('/message-templates')
        ? []
        : { items: [], next_cursor: null }
      return {
        ok: true,
        status: 200,
        json: () => Promise.resolve(body),
      } as Response
    })

    await user.click(screen.getByRole('button', { name: /^E-mails/ }))

    expect(
      await screen.findByRole('heading', { name: 'Preparação de e-mails' }),
    ).toBeVisible()
    expect(screen.getByText('Envio desativado')).toBeVisible()
    expect(
      screen.queryByRole('button', { name: /enviar/i }),
    ).not.toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3))
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/message-templates',
      expect.objectContaining({
        headers: { Authorization: 'Bearer raw-secret-token' },
      }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/email-recipient-candidates?status=pending&limit=20',
      expect.objectContaining({
        headers: { Authorization: 'Bearer raw-secret-token' },
      }),
    )
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
      screen.queryByRole('heading', {
        name: 'Bem-vindo, Proprietário Delta Force',
      }),
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
      screen.queryByRole('heading', {
        name: 'Bem-vindo, Proprietário Delta Force',
      }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('signs out locally when the server session reaches its expiry', async () => {
    await signIn(250)

    expect(
      await screen.findByRole('button', { name: 'Entrar' }, { timeout: 2_000 }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', {
        name: 'Bem-vindo, Proprietário Delta Force',
      }),
    ).not.toBeInTheDocument()
  })
})
