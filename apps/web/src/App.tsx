import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginPage } from './auth/LoginPage'
import { SetupPage } from './auth/SetupPage'

function Root() {
  const { status, user, logout, retry } = useAuth()

  if (status === 'checking-setup') return <p>Carregando…</p>
  if (status === 'setup-required') return <SetupPage />
  if (status === 'signed-out') return <LoginPage />
  if (status === 'unavailable') {
    return (
      <main>
        <h1>Delta Force CRM</h1>
        <p role="alert">Não foi possível conectar ao serviço local.</p>
        <button type="button" onClick={retry}>
          Tentar novamente
        </button>
      </main>
    )
  }
  if (user === null) return null

  return (
    <main>
      <h1>Delta Force CRM</h1>
      <p>Olá, {user.full_name}.</p>
      <button type="button" onClick={() => void logout()}>
        Sair
      </button>
    </main>
  )
}

export function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}
