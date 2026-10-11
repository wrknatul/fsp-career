// Safe readers for Fact.value (the contract keeps it an open record).
// Each reader returns a fully typed object with defaults, so pages never cast `unknown`.

import type {
  AchievementFactValue,
  AchievementResult,
  CompetitionLevel,
  Discipline,
  ExperienceFactValue,
  ExperiencePosition,
  Fact,
  RankFactValue,
  RoleFactValue,
  SkillFactValue,
  SportRank,
  Verification,
} from '@/api/types'

type Raw = Record<string, unknown>

function str(raw: Raw, key: string): string | null {
  const value = raw[key]
  return typeof value === 'string' && value !== '' ? value : null
}

function num(raw: Raw, key: string): number | null {
  const value = raw[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function isRecord(value: unknown): value is Raw {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function skillFactValue(fact: Fact): SkillFactValue {
  const level = num(fact.value, 'level')
  const score = num(fact.value, 'score')
  const safeLevel: 1 | 2 | 3 = level === 2 ? 2 : level === 3 ? 3 : 1
  return score === null ? { level: safeLevel } : { level: safeLevel, score }
}

export function experienceFactValue(fact: Fact): ExperienceFactValue {
  const years = num(fact.value, 'years') ?? 0
  const rawPositions = fact.value.positions
  const positions: ExperiencePosition[] = []
  if (Array.isArray(rawPositions)) {
    for (const entry of rawPositions) {
      if (!isRecord(entry)) {
        continue
      }
      positions.push({
        title: str(entry, 'title') ?? 'Должность',
        company: str(entry, 'company'),
        period: str(entry, 'period') ?? '',
        years: num(entry, 'years') ?? 0,
      })
    }
  }
  return { years, positions }
}

export function achievementFactValue(fact: Fact): AchievementFactValue {
  const raw = fact.value
  const result = str(raw, 'result')
  return {
    title: str(raw, 'title') ?? fact.title,
    discipline: str(raw, 'discipline') as Discipline | null,
    level: (str(raw, 'level') ?? 'regional') as CompetitionLevel,
    place: num(raw, 'place'),
    result: (result === 'winner' || result === 'prize' ? result : 'participant') as AchievementResult,
    date: str(raw, 'date'),
    year: num(raw, 'year'),
    team_name: str(raw, 'team_name'),
    team_role: str(raw, 'team_role'),
    participants_total: num(raw, 'participants_total'),
    document_url: str(raw, 'document_url'),
  }
}

export function rankFactValue(fact: Fact): RankFactValue {
  const raw = fact.value
  return {
    rank: (str(raw, 'rank') ?? 'third') as SportRank,
    discipline: str(raw, 'discipline') as Discipline | null,
    assigned_at: str(raw, 'assigned_at'),
    order_no: str(raw, 'order_no'),
  }
}

export function roleFactValue(fact: Fact): RoleFactValue {
  return { reason: str(fact.value, 'reason') ?? '' }
}

/** Year of an achievement fact: explicit year, else the year of `date`, else null. */
export function achievementYear(fact: Fact): number | null {
  const value = achievementFactValue(fact)
  if (value.year !== null) {
    return value.year
  }
  if (value.date !== null) {
    const parsed = Number(value.date.slice(0, 4))
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const VERIFICATION_RANK: Record<Verification, number> = { verified: 4, tested: 3, parsed: 2, declared: 1 }

/** Sort key: stronger confirmation first. */
export function verificationRank(verification: Verification): number {
  return VERIFICATION_RANK[verification]
}

/** True when the key is a fact the candidate added by hand (removable). */
export function isManualAchievement(fact: Fact): boolean {
  return fact.kind === 'achievement' && fact.source === 'self'
}

/** True for http(s) links only: protects href bindings from javascript: URLs. */
export function isHttpUrl(value: string | null | undefined): boolean {
  if (typeof value !== 'string') {
    return false
  }
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}
