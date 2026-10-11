import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchMe, login as loginRequest, register as registerRequest } from '@/api/auth'
import { clearStoredToken, getStoredToken, isApiRequestError, storeToken } from '@/api/client'
import type { AuthResponse, LoginRequest, RegisterRequest, Role, User } from '@/api/types'
import { demoAccount } from '@/utils/demo'

export const HOME_PATH: Record<Role, string> = {
  candidate: '/candidate',
  employer: '/employer',
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getStoredToken())
  const user = ref<User | null>(null)
  /** true once the session restore attempt (if any) has finished. */
  const initialized = ref(false)
  let restorePromise: Promise<void> | null = null

  const isAuthenticated = computed(() => token.value !== null && user.value !== null)
  const role = computed<Role | null>(() => user.value?.role ?? null)
  /** Cabinet root of the current role; '/login' for a guest. */
  const homePath = computed(() => (user.value === null ? '/login' : HOME_PATH[user.value.role]))
  const displayName = computed(() => user.value?.full_name ?? '')

  function applySession(response: AuthResponse): void {
    storeToken(response.access_token)
    token.value = response.access_token
    user.value = response.user
    initialized.value = true
  }

  async function login(body: LoginRequest): Promise<User> {
    const response = await loginRequest(body)
    applySession(response)
    return response.user
  }

  async function register(body: RegisterRequest): Promise<User> {
    const response = await registerRequest(body)
    applySession(response)
    return response.user
  }

  /** One-click demo login with the seeded accounts (see utils/demo.ts). */
  async function demoLogin(demoRole: Role): Promise<User> {
    return login(demoAccount(demoRole))
  }

  function logout(): void {
    clearStoredToken()
    token.value = null
    user.value = null
    restorePromise = null
    initialized.value = true
  }

  /**
   * Restore the session from the stored token via GET /auth/me.
   * Safe to call repeatedly: the request runs once. Never throws.
   * 401 -> token dropped (guest). Network/server failure -> token kept, user stays empty.
   */
  function restore(): Promise<void> {
    if (initialized.value) {
      return Promise.resolve()
    }
    if (restorePromise !== null) {
      return restorePromise
    }
    if (token.value === null) {
      initialized.value = true
      return Promise.resolve()
    }
    restorePromise = fetchMe()
      .then((me) => {
        user.value = me
      })
      .catch((err: unknown) => {
        if (isApiRequestError(err) && err.status === 401) {
          clearStoredToken()
          token.value = null
        }
        user.value = null
      })
      .finally(() => {
        initialized.value = true
        restorePromise = null
      })
    return restorePromise
  }

  /** Replace the cached user (e.g. after the name was changed in the profile). */
  function setUser(next: User): void {
    user.value = next
  }

  return {
    token,
    user,
    initialized,
    isAuthenticated,
    role,
    homePath,
    displayName,
    login,
    register,
    demoLogin,
    logout,
    restore,
    setUser,
  }
})
