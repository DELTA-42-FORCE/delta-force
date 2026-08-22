import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { apiFetch, ApiError } from '../lib/apiClient'
import {
  login as loginRequest,
  logout as logoutRequest,
  requiresSetup,
  setupOwner,
} from './authApi'
import type { AuthenticatedUser, SetupOwnerInput } from './types'

type AuthStatus =
  | 'checking-setup'
  | 'setup-required'
  | 'signed-out'
  | 'signed-in'
  | 'unavailable'

interface AuthContextValue {
  status: AuthStatus
  user: AuthenticatedUser | null
  authenticatedGet: <T>(path: string) => Promise<T>
  login: (email: string, password: string) => Promise<void>
  setup: (input: SetupOwnerInput) => Promise<void>
  logout: () => Promise<void>
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [sessionExpiresAt, setSessionExpiresAt] = useState<number | null>(null)
  const [status, setStatus] = useState<AuthStatus>('checking-setup')
  const [checkSequence, setCheckSequence] = useState(0)

  const clearSession = useCallback(() => {
    setToken(null)
    setUser(null)
    setSessionExpiresAt(null)
    setStatus('signed-out')
  }, [])

  useEffect(() => {
    let active = true
    requiresSetup()
      .then((isRequired) => {
        if (active) setStatus(isRequired ? 'setup-required' : 'signed-out')
      })
      .catch(() => {
        if (active) setStatus('unavailable')
      })
    return () => {
      active = false
    }
  }, [checkSequence])

  const acceptLogin = useCallback(
    (result: {
      session_token: string
      expires_at: string
      user: AuthenticatedUser
    }) => {
      const expiresAt = Date.parse(result.expires_at)
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
        clearSession()
        throw new Error('server returned an invalid session expiry')
      }
      setToken(result.session_token)
      setUser(result.user)
      setSessionExpiresAt(expiresAt)
      setStatus('signed-in')
    },
    [clearSession],
  )

  useEffect(() => {
    if (status !== 'signed-in' || sessionExpiresAt === null) return

    const remainingMilliseconds = sessionExpiresAt - Date.now()
    if (remainingMilliseconds <= 0) {
      clearSession()
      return
    }

    const timeout = window.setTimeout(clearSession, remainingMilliseconds)
    return () => window.clearTimeout(timeout)
  }, [clearSession, sessionExpiresAt, status])

  const login = useCallback(
    async (email: string, password: string) => {
      acceptLogin(await loginRequest(email, password))
    },
    [acceptLogin],
  )

  const setup = useCallback(
    async (input: SetupOwnerInput) => {
      acceptLogin(await setupOwner(input))
    },
    [acceptLogin],
  )

  const logout = useCallback(async () => {
    const sessionToken = token
    clearSession()
    if (sessionToken === null) return

    try {
      await logoutRequest(sessionToken)
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error
    }
  }, [clearSession, token])

  const authenticatedGet = useCallback(
    async <T,>(path: string): Promise<T> => {
      if (token === null) throw new ApiError(401, 'session is not available')

      try {
        return await apiFetch<T>(path, { token })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) clearSession()
        throw error
      }
    },
    [clearSession, token],
  )

  const retry = useCallback(() => {
    setStatus('checking-setup')
    setCheckSequence((current) => current + 1)
  }, [])

  const value = useMemo(
    () => ({
      status,
      user,
      authenticatedGet,
      login,
      setup,
      logout,
      retry,
    }),
    [status, user, authenticatedGet, login, setup, logout, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null)
    throw new Error('useAuth must be used within AuthProvider')
  return context
}
