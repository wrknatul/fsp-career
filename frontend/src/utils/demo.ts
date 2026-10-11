// One-click demo login settings. Defaults can be overridden at build time with VITE_DEMO_*.

import type { Role } from '@/api/types'

function envString(raw: unknown, fallback: string): string {
  return typeof raw === 'string' && raw.trim() !== '' ? raw.trim() : fallback
}

const rawMode: unknown = import.meta.env.VITE_DEMO_MODE
const rawCandidateEmail: unknown = import.meta.env.VITE_DEMO_CANDIDATE_EMAIL
const rawEmployerEmail: unknown = import.meta.env.VITE_DEMO_EMPLOYER_EMAIL
const rawPassword: unknown = import.meta.env.VITE_DEMO_PASSWORD

/** false when VITE_DEMO_MODE=false: demo buttons are hidden everywhere. */
export const DEMO_MODE: boolean = !(typeof rawMode === 'string' && rawMode.trim().toLowerCase() === 'false')

const DEMO_ACCOUNTS: Record<Role, { email: string; password: string }> = {
  candidate: {
    email: envString(rawCandidateEmail, 'demo.candidate@fsp-career.test'),
    password: envString(rawPassword, 'demo12345'),
  },
  employer: {
    email: envString(rawEmployerEmail, 'demo.employer@fsp-career.test'),
    password: envString(rawPassword, 'demo12345'),
  },
}

export function demoAccount(role: Role): { email: string; password: string } {
  return DEMO_ACCOUNTS[role]
}

/** FSP ID that exists in the demo registry (used as a hint on the FSP page). */
export const DEMO_FSP_ID = 'FSP-2024-00117'
