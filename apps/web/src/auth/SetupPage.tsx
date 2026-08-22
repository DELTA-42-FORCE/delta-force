import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './AuthContext'

export function SetupPage() {
  const { setup, retry } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (password !== confirmation) {
      setError('As senhas precisam ser iguais.')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await setup({ email, full_name: fullName, password })
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 409) {
        retry()
      } else {
        setError('Não foi possível concluir a configuração. Tente novamente.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Primeiro acesso"
      title="Configure sua conta"
      description="Crie o acesso exclusivo do proprietário deste computador."
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="full-name">Nome completo</label>
          <input
            id="full-name"
            autoComplete="name"
            minLength={2}
            required
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Como você quer ser chamado"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-email">E-mail</label>
          <input
            id="setup-email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="seu@email.com"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-password">Senha</label>
          <input
            id="setup-password"
            type="password"
            autoComplete="new-password"
            aria-describedby="password-help"
            minLength={12}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Crie uma senha segura"
          />
          <small id="password-help">Use pelo menos 12 caracteres.</small>
        </div>
        <div className="field">
          <label htmlFor="setup-password-confirmation">Confirmar senha</label>
          <input
            id="setup-password-confirmation"
            type="password"
            autoComplete="new-password"
            minLength={12}
            required
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder="Digite a mesma senha"
          />
        </div>
        {error !== null && (
          <p className="feedback feedback--error" role="alert">
            {error}
          </p>
        )}
        <button
          className="primary-button"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Configurando…' : 'Criar conta e entrar'}
        </button>
        <p className="privacy-note">
          Sua senha não é enviada para serviços externos.
        </p>
      </form>
    </AuthLayout>
  )
}
