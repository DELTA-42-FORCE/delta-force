import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './AuthContext'

export function LoginPage({ notice }: { notice?: string | null }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
    } catch (submitError) {
      setError(
        submitError instanceof ApiError && submitError.status === 401
          ? 'E-mail ou senha inválidos.'
          : 'Não foi possível entrar agora. Tente novamente.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Acesso do proprietário"
      title="Bem-vindo de volta"
      description="Entre para acessar o CRM neste computador."
    >
      {notice != null && (
        <p className="feedback feedback--warning" role="alert">
          {notice}
        </p>
      )}
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            autoFocus
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="seu@email.com"
          />
        </div>
        <div className="field">
          <label htmlFor="password">Senha</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Digite sua senha"
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
          {isSubmitting ? 'Entrando…' : 'Entrar'}
        </button>
        <p className="privacy-note">A sessão fica somente neste aplicativo.</p>
      </form>
    </AuthLayout>
  )
}
