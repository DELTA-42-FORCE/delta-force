export interface ManagedUser {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
}

export interface CreateUserInput {
  email: string
  full_name: string
  password: string
  is_admin: boolean
}
