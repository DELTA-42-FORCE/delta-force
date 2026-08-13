import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginPage } from './auth/LoginPage'
import { UsersPage } from './users/UsersPage'

function AuthenticatedApp() {
  const { user, logout } = useAuth()
  if (user === null) {
    return null
  }

  return (
    <main>
      <header>
        <h1>Delta Force CRM</h1>
        <p>
          {user.full_name} ({user.email})
        </p>
        <button type="button" onClick={() => void logout()}>
          Sair
        </button>
      </header>

      {user.is_admin ? (
        <UsersPage />
      ) : (
        <p>Sua conta não tem permissão de administrador.</p>
      )}
    </main>
  )
}

function Root() {
  const { status } = useAuth()

  if (status === 'restoring') {
    return <p>Carregando…</p>
  }

  if (status === 'signed-out') {
    return <LoginPage />
  }

  return <AuthenticatedApp />
}

export function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}
