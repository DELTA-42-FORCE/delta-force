import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './AuthContext'

type SetupField = 'fullName' | 'email' | 'password' | 'confirmation'

const VALIDATION_MESSAGE =
  'Revise os campos indicados. O nome deve ter entre 2 e 200 caracteres; use um e-mail válido e uma senha de 12 a 72 caracteres, com no máximo 72 bytes.'

const EMPTY_INVALID_FIELDS: Record<SetupField, boolean> = {
  fullName: false,
  email: false,
  password: false,
  confirmation: false,
}

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

export function SetupPage() {
  const { setup, retry } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [invalidFields, setInvalidFields] = useState(EMPTY_INVALID_FIELDS)

  function clearValidation() {
    setError(null)
    setInvalidFields(EMPTY_INVALID_FIELDS)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const passwordBytes = new TextEncoder().encode(password).length
    const nextInvalidFields = {
      fullName: fullName.length < 2 || fullName.length > 200,
      email: !isValidEmail(email),
      password:
        password.length < 12 || password.length > 72 || passwordBytes > 72,
      confirmation: password !== confirmation,
    }
    if (Object.values(nextInvalidFields).some(Boolean)) {
      setInvalidFields(nextInvalidFields)
      setError(
        nextInvalidFields.confirmation &&
          !nextInvalidFields.fullName &&
          !nextInvalidFields.email &&
          !nextInvalidFields.password
          ? 'As senhas precisam ser iguais.'
          : VALIDATION_MESSAGE,
      )
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await setup({ email, full_name: fullName, password })
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 409) {
        retry()
      } else if (
        submitError instanceof ApiError &&
        submitError.status === 422
      ) {
        setInvalidFields({
          fullName: true,
          email: true,
          password: true,
          confirmation: false,
        })
        setError(VALIDATION_MESSAGE)
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
      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="full-name">Nome completo</label>
          <input
            id="full-name"
            autoComplete="name"
            aria-describedby={
              invalidFields.fullName ? 'setup-validation-error' : undefined
            }
            aria-invalid={invalidFields.fullName || undefined}
            minLength={2}
            maxLength={200}
            required
            value={fullName}
            onChange={(event) => {
              clearValidation()
              setFullName(event.target.value)
            }}
            placeholder="Como você quer ser chamado"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-email">E-mail</label>
          <input
            id="setup-email"
            type="email"
            autoComplete="username"
            aria-describedby={
              invalidFields.email ? 'setup-validation-error' : undefined
            }
            aria-invalid={invalidFields.email || undefined}
            required
            value={email}
            onChange={(event) => {
              clearValidation()
              setEmail(event.target.value)
            }}
            placeholder="seu@email.com"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-password">Senha</label>
          <input
            id="setup-password"
            type="password"
            autoComplete="new-password"
            aria-describedby={
              invalidFields.password
                ? 'password-help setup-validation-error'
                : 'password-help'
            }
            aria-invalid={invalidFields.password || undefined}
            minLength={12}
            required
            value={password}
            onChange={(event) => {
              clearValidation()
              setPassword(event.target.value)
            }}
            placeholder="Crie uma senha segura"
          />
          <small id="password-help">
            Use de 12 a 72 caracteres e no máximo 72 bytes. Acentos podem ocupar
            mais de um byte.
          </small>
        </div>
        <div className="field">
          <label htmlFor="setup-password-confirmation">Confirmar senha</label>
          <input
            id="setup-password-confirmation"
            type="password"
            autoComplete="new-password"
            aria-describedby={
              invalidFields.confirmation ? 'setup-validation-error' : undefined
            }
            aria-invalid={invalidFields.confirmation || undefined}
            minLength={12}
            required
            value={confirmation}
            onChange={(event) => {
              clearValidation()
              setConfirmation(event.target.value)
            }}
            placeholder="Digite a mesma senha"
          />
        </div>
        {error !== null && (
          <p
            className="feedback feedback--error"
            id="setup-validation-error"
            role="alert"
          >
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
