import type { Role } from '@/api/types'

const HOME: Record<Role, string> = { candidate: '/candidate', employer: '/employer' }

/**
 * Where to go after login: the `redirect` query value if it is an in-app path of the user's own
 * cabinet, otherwise the cabinet root. Protects against open redirects ("//evil.example", "https:...")
 * and against sending an employer into /candidate/*.
 */
export function safeRedirect(raw: unknown, role: Role): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string') {
    return HOME[role]
  }
  const prefix = HOME[role]
  const insideCabinet = value === prefix || value.startsWith(`${prefix}/`) || value.startsWith(`${prefix}?`)
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\') || !insideCabinet) {
    return HOME[role]
  }
  return value
}
