import { useState } from 'react'

import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginPage } from './auth/LoginPage'
import { SetupPage } from './auth/SetupPage'

function Root() {
  const { status, user, logout, retry } = useAuth()
  const [logoutNotice, setLogoutNotice] = useState<string | null>(null)

  async function handleLogout() {
    setLogoutNotice(null)
    try {
      await logout()
    } catch {
      setLogoutNotice(
        'Você saiu deste aplicativo, mas não foi possível confirmar o encerramento no serviço local.',
      )
    }
  }

  if (status === 'checking-setup') return <p>Carregando…</p>
  if (status === 'setup-required') return <SetupPage />
  if (status === 'signed-out') return <LoginPage notice={logoutNotice} />
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
      <button type="button" onClick={() => void handleLogout()}>
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
