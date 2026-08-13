export interface AuthenticatedUser {
  id: string
  email: string
  full_name: string
  is_admin: boolean
}

export interface LoginResult {
  session_token: string
  expires_at: string
  user: AuthenticatedUser
}
