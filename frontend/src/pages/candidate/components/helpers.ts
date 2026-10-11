// Small shared helpers of the candidate cabinet pages (no UI, no requests).

import { ApiRequestError } from '@/api/client'
import type { Fact, FactKind, FspTeamRole, Source } from '@/api/types'

// ---------- FSP team roles (the "team_role" string inside an FSP achievement fact) ----------

const FSP_TEAM_ROLE_TITLES: Record<FspTeamRole, string> = {
  captain: 'Капитан',
  backend: 'Backend в команде',
  frontend: 'Frontend в команде',
  ml: 'ML в команде',
  analyst: 'Аналитик в команде',
  designer: 'Дизайнер в команде',
  member: 'Участник команды',
}

function isFspTeamRole(value: string): value is FspTeamRole {
  return Object.prototype.hasOwnProperty.call(FSP_TEAM_ROLE_TITLES, value)
}

/** Russian caption of a team role from the registry; unknown values come back as-is. */
export function fspTeamRoleTitle(raw: string | null): string | null {
  if (raw === null) {
    return null
  }
  return isFspTeamRole(raw) ? FSP_TEAM_ROLE_TITLES[raw] : raw
}

// ---------- Name preview ----------

/**
 * How employers see the candidate before an offer is accepted
 * (mirrors backend `display_name`): "Смирнов Алексей Игоревич" -> "Алексей С.".
 */
export function previewDisplayName(fullName: string): string {
  const words = fullName.split(/\s+/).filter((word) => word !== '')
  if (words.length === 0) {
    return ''
  }
  if (words.length === 1) {
    return words[0]
  }
  return `${words[1]} ${words[0].charAt(0).toUpperCase()}.`
}

// ---------- Facts ----------

/** Facts of a kind (and optionally of a source), in the order the server sent them. */
export function pickFacts(facts: readonly Fact[], kind: FactKind, source?: Source): Fact[] {
  return facts.filter((fact) => fact.kind === kind && (source === undefined || fact.source === source))
}

// ---------- sessionStorage (every access is guarded: the storage may be blocked) ----------

export function sessionGet(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key)
  } catch {
    return null
  }
}

export function sessionSet(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value)
  } catch {
    // Storage is blocked: the feature that needs it degrades silently.
  }
}

export function sessionRemove(key: string): void {
  try {
    window.sessionStorage.removeItem(key)
  } catch {
    // Nothing to remove if storage is blocked.
  }
}

// ---------- FSP link errors: every code gets its own plain text ----------

export type LinkErrorView = {
  text: string
  /** Show a link to the questionnaire next to the text. */
  toProfile: boolean
  /** The profile on screen is probably stale: reload it. */
  reload: boolean
}

/**
 * Own text for each error of POST /candidate/fsp/link.
 * Returns null for codes without a special text: the caller falls back to the server message.
 */
export function describeLinkError(err: unknown): LinkErrorView | null {
  if (!(err instanceof ApiRequestError)) {
    return null
  }
  switch (err.error_code) {
    case 'PROFILE_INCOMPLETE':
      return {
        text: 'В анкете не хватает ФИО или даты рождения. Мы сверяем их с реестром, поэтому сначала заполните анкету.',
        toProfile: true,
        reload: false,
      }
    case 'RATE_LIMITED':
      return {
        text: 'Слишком много попыток: можно не больше пяти в час. Подождите немного и попробуйте снова.',
        toProfile: false,
        reload: false,
      }
    case 'FSP_ATHLETE_NOT_FOUND':
      return {
        text: 'Спортсмена с таким ФСП ID нет в реестре. Проверьте номер: он выглядит как FSP-2024-00117.',
        toProfile: false,
        reload: false,
      }
    case 'FSP_ALREADY_LINKED':
      if (err.details.linked_to_you === true) {
        return {
          text: 'Этот ФСП ID уже привязан к вашему аккаунту. Мы обновили страницу.',
          toProfile: false,
          reload: true,
        }
      }
      return {
        text: 'Этот ФСП ID уже привязан к другому аккаунту. Если это ваш номер, напишите в поддержку ФСП.',
        toProfile: false,
        reload: false,
      }
    case 'FSP_IDENTITY_MISMATCH':
      return {
        text: 'ФИО или дата рождения в анкете не совпали с записью в реестре. Проверьте анкету и попробуйте снова.',
        toProfile: true,
        reload: false,
      }
    default:
      return null
  }
}
