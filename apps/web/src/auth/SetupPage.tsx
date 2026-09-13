import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type RefObject,
} from 'react'

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

function isValidPassword(value: string): boolean {
  const passwordBytes = new TextEncoder().encode(value).length
  return value.length >= 12 && value.length <= 72 && passwordBytes <= 72
}

export function SetupPage() {
  const { setup, retry } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [invalidFields, setInvalidFields] = useState(EMPTY_INVALID_FIELDS)
  const fullNameRef = useRef<HTMLInputElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const confirmationRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!hasAttemptedSubmit) {
      return
    }

    const hasInvalidField = Object.values(invalidFields).some(Boolean)
    const isValidationError =
      error === VALIDATION_MESSAGE || error === 'As senhas precisam ser iguais.'

    if (hasInvalidField) {
      const onlyConfirmationIsInvalid =
        invalidFields.confirmation &&
        !invalidFields.fullName &&
        !invalidFields.email &&
        !invalidFields.password
      const nextError = onlyConfirmationIsInvalid
        ? 'As senhas precisam ser iguais.'
        : VALIDATION_MESSAGE

      if (error !== nextError) {
        setError(nextError)
      }
    } else if (isValidationError) {
      setError(null)
    }
  }, [error, hasAttemptedSubmit, invalidFields])

  function revalidateFields(validation: Partial<Record<SetupField, boolean>>) {
    if (!hasAttemptedSubmit) {
      return
    }

    setInvalidFields((current) => {
      const next = { ...current }

      for (const field of Object.keys(validation) as SetupField[]) {
        next[field] = validation[field] ?? current[field]
      }

      return next
    })
  }

  function focusFirstInvalid(fields: Record<SetupField, boolean>) {
    const fieldRefs: Record<SetupField, RefObject<HTMLInputElement | null>> = {
      fullName: fullNameRef,
      email: emailRef,
      password: passwordRef,
      confirmation: confirmationRef,
    }
    const firstInvalidField = (Object.keys(fields) as SetupField[]).find(
      (field) => fields[field],
    )

    if (firstInvalidField !== undefined) {
      fieldRefs[firstInvalidField].current?.focus()
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setHasAttemptedSubmit(true)
    const nextInvalidFields = {
      fullName: fullName.length < 2 || fullName.length > 200,
      email: !isValidEmail(email),
      password: !isValidPassword(password),
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
      focusFirstInvalid(nextInvalidFields)
      return
    }
    setError(null)
    setInvalidFields(EMPTY_INVALID_FIELDS)
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
        fullNameRef.current?.focus()
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
            ref={fullNameRef}
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
              const value = event.target.value
              setFullName(value)
              revalidateFields({
                fullName: value.length < 2 || value.length > 200,
              })
            }}
            placeholder="Como você quer ser chamado"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-email">E-mail</label>
          <input
            id="setup-email"
            ref={emailRef}
            type="email"
            autoComplete="username"
            aria-describedby={
              invalidFields.email ? 'setup-validation-error' : undefined
            }
            aria-invalid={invalidFields.email || undefined}
            required
            value={email}
            onChange={(event) => {
              const value = event.target.value
              setEmail(value)
              revalidateFields({ email: !isValidEmail(value) })
            }}
            placeholder="seu@email.com"
          />
        </div>
        <div className="field">
          <label htmlFor="setup-password">Senha</label>
          <input
            id="setup-password"
            ref={passwordRef}
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
              const value = event.target.value
              setPassword(value)
              revalidateFields({
                password: !isValidPassword(value),
                confirmation: value !== confirmation,
              })
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
            ref={confirmationRef}
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
              const value = event.target.value
              setConfirmation(value)
              revalidateFields({ confirmation: password !== value })
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
