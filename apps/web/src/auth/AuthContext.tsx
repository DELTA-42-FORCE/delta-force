import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { ApiError } from '../lib/apiClient'
import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
} from './authApi'
import type { AuthenticatedUser } from './types'

const SESSION_TOKEN_STORAGE_KEY = 'delta-force:session-token'

type AuthStatus = 'restoring' | 'signed-out' | 'signed-in'

interface AuthContextValue {
  status: AuthStatus
  user: AuthenticatedUser | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>('restoring')

  useEffect(() => {
    const storedToken = window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY)
    if (storedToken === null) {
      setStatus('signed-out')
      return
    }

    fetchCurrentUser(storedToken)
      .then((restoredUser) => {
        setToken(storedToken)
        setUser(restoredUser)
        setStatus('signed-in')
      })
      .catch(() => {
        window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY)
        setStatus('signed-out')
      })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginRequest(email, password)
    window.localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, result.session_token)
    setToken(result.session_token)
    setUser(result.user)
    setStatus('signed-in')
  }, [])

  const logout = useCallback(async () => {
    if (token !== null) {
      try {
        await logoutRequest(token)
      } catch (error) {
        // A sessão pode já ter expirado no servidor; seguimos limpando o
        // estado local mesmo assim, exceto se o erro for inesperado.
        if (!(error instanceof ApiError)) {
          throw error
        }
      }
    }
    window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY)
    setToken(null)
    setUser(null)
    setStatus('signed-out')
  }, [token])

  const value = useMemo(
    () => ({ status, user, token, login, logout }),
    [status, user, token, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
