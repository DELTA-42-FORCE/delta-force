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
  login: (email: string, password: string) => Promise<void>
  setup: (input: SetupOwnerInput) => Promise<void>
  logout: () => Promise<void>
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>('checking-setup')
  const [checkSequence, setCheckSequence] = useState(0)

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
    (result: { session_token: string; user: AuthenticatedUser }) => {
      setToken(result.session_token)
      setUser(result.user)
      setStatus('signed-in')
    },
    [],
  )

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
    if (token !== null) {
      try {
        await logoutRequest(token)
      } catch (error) {
        if (!(error instanceof ApiError)) throw error
      }
    }
    setToken(null)
    setUser(null)
    setStatus('signed-out')
  }, [token])

  const retry = useCallback(() => {
    setStatus('checking-setup')
    setCheckSequence((current) => current + 1)
  }, [])

  const value = useMemo(
    () => ({ status, user, login, setup, logout, retry }),
    [status, user, login, setup, logout, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null)
    throw new Error('useAuth must be used within AuthProvider')
  return context
}
