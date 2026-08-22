import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
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
    <main>
      <h1>Configurar Delta Force CRM</h1>
      <p>Crie a conta do proprietário deste computador.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="full-name">Nome completo</label>
        <input
          id="full-name"
          autoComplete="name"
          minLength={2}
          required
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
        <label htmlFor="setup-email">E-mail</label>
        <input
          id="setup-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <label htmlFor="setup-password">Senha</label>
        <input
          id="setup-password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <label htmlFor="setup-password-confirmation">Confirmar senha</label>
        <input
          id="setup-password-confirmation"
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
        />
        {error !== null && <p role="alert">{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Configurando…' : 'Criar conta e entrar'}
        </button>
      </form>
    </main>
  )
}
