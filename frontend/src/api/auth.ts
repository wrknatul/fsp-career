import { http } from './client'
import type { AuthResponse, LoginRequest, RegisterRequest, User } from './types'

/** POST /auth/register -> 201 */
export function register(body: RegisterRequest): Promise<AuthResponse> {
  return http.post<AuthResponse>('/auth/register', body, false)
}

/** POST /auth/login */
export function login(body: LoginRequest): Promise<AuthResponse> {
  return http.post<AuthResponse>('/auth/login', body, false)
}

/** GET /auth/me */
export function fetchMe(): Promise<User> {
  return http.get<User>('/auth/me')
}
