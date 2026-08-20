export interface AuthenticatedUser {
  id: string
  email: string
  full_name: string
}

export interface LoginResult {
  session_token: string
  expires_at: string
  user: AuthenticatedUser
}

export interface SetupOwnerInput {
  email: string
  full_name: string
  password: string
}
