import { useEffect, useState, type FormEvent } from 'react'

import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../lib/apiClient'
import { createUser, listUsers, setUserActive } from './usersApi'
import type { ManagedUser } from './types'

type ListState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; users: ManagedUser[] }

export function UsersPage() {
  const { token } = useAuth()
  const [listState, setListState] = useState<ListState>({ status: 'loading' })
  const [pendingUserId, setPendingUserId] = useState<string | null>(null)

  async function reload(currentToken: string) {
    setListState({ status: 'loading' })
    try {
      const users = await listUsers(currentToken)
      setListState({ status: 'loaded', users })
    } catch {
      setListState({
        status: 'error',
        message: 'Não foi possível carregar os usuários.',
      })
    }
  }

  useEffect(() => {
    if (token !== null) {
      void reload(token)
    }
  }, [token])

  async function handleToggleActive(user: ManagedUser) {
    if (token === null) {
      return
    }

    setPendingUserId(user.id)
    try {
      await setUserActive(token, user.id, !user.is_active)
      await reload(token)
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 409
          ? 'Um administrador não pode desativar a própria conta.'
          : 'Não foi possível atualizar o usuário.'
      window.alert(message)
    } finally {
      setPendingUserId(null)
    }
  }

  if (token === null) {
    return null
  }

  return (
    <section>
      <h2>Usuários autorizados</h2>
      <CreateUserForm token={token} onCreated={() => reload(token)} />

      {listState.status === 'loading' && <p>Carregando usuários…</p>}
      {listState.status === 'error' && <p role="alert">{listState.message}</p>}
      {listState.status === 'loaded' && listState.users.length === 0 && (
        <p>Nenhum usuário cadastrado ainda.</p>
      )}
      {listState.status === 'loaded' && listState.users.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Papel</th>
              <th>Status</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {listState.users.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name}</td>
                <td>{user.email}</td>
                <td>{user.is_admin ? 'Administrador' : 'Usuário'}</td>
                <td>{user.is_active ? 'Ativo' : 'Inativo'}</td>
                <td>
                  <button
                    type="button"
                    disabled={pendingUserId === user.id}
                    onClick={() => handleToggleActive(user)}
                  >
                    {user.is_active ? 'Desativar' : 'Ativar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function CreateUserForm({
  token,
  onCreated,
}: {
  token: string
  onCreated: () => void
}) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await createUser(token, {
        email,
        full_name: fullName,
        password,
        is_admin: isAdmin,
      })
      setEmail('')
      setFullName('')
      setPassword('')
      setIsAdmin(false)
      onCreated()
    } catch (submitError) {
      const message =
        submitError instanceof ApiError && submitError.status === 409
          ? 'Já existe uma conta com esse e-mail.'
          : 'Não foi possível criar o usuário.'
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3>Novo usuário</h3>
      <div>
        <label htmlFor="new-user-full-name">Nome</label>
        <input
          id="new-user-full-name"
          required
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="new-user-email">E-mail</label>
        <input
          id="new-user-email"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="new-user-password">Senha provisória</label>
        <input
          id="new-user-password"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="new-user-is-admin">
          <input
            id="new-user-is-admin"
            type="checkbox"
            checked={isAdmin}
            onChange={(event) => setIsAdmin(event.target.checked)}
          />
          Administrador
        </label>
      </div>
      {error !== null && <p role="alert">{error}</p>}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Criando…' : 'Criar usuário'}
      </button>
    </form>
  )
}
