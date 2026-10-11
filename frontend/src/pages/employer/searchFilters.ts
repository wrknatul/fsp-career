// Search filters of the employer cabinet: one shape, shared by the dashboard (links into the search),
// the search page (state lives in the address bar) and the vacancies page (links "Подобрать кандидатов").
//
// URL parameters use the names of MatchQuery fields. Lists are comma-separated, booleans are "1":
//   /employer/search?stacks=backend,frontend&grades=junior&skills_required=python&fsp_verified_only=1&text=...

import type { LocationQuery, LocationQueryRaw, RouteLocationRaw } from 'vue-router'

import type { Discipline, Grade, MatchQuery, Stack, TeamRole, WorkFormat } from '@/api/types'
import { DISCIPLINE_ORDER, GRADE_ORDER, STACK_ORDER, TEAM_ROLE_ORDER, WORK_FORMAT_ORDER } from '@/utils/labels'

export type SearchFilters = {
  stacks: Stack[]
  grades: Grade[]
  team_roles: TeamRole[]
  work_formats: WorkFormat[]
  city: string | null
  skills_required: string[]
  skills_optional: string[]
  strict_skills: boolean
  fsp_verified_only: boolean
  confirmed_only: boolean
  disciplines: Discipline[]
  salary_max: number | null
  text: string
  vacancy_id: number | null
}

/** Server limits (backend MatchQuery). */
export const TEXT_MAX_LENGTH = 2000
export const MAX_SALARY = 100_000_000
const MAX_SKILLS = 30
const MAX_CITY_LENGTH = 100
const SKILL_ID_PATTERN = /^[a-z0-9][a-z0-9+#._-]{0,63}$/

export function emptyFilters(): SearchFilters {
  return {
    stacks: [],
    grades: [],
    team_roles: [],
    work_formats: [],
    city: null,
    skills_required: [],
    skills_optional: [],
    strict_skills: false,
    fsp_verified_only: false,
    confirmed_only: false,
    disciplines: [],
    salary_max: null,
    text: '',
    vacancy_id: null,
  }
}

export function cloneFilters(filters: SearchFilters): SearchFilters {
  return {
    ...filters,
    stacks: [...filters.stacks],
    grades: [...filters.grades],
    team_roles: [...filters.team_roles],
    work_formats: [...filters.work_formats],
    skills_required: [...filters.skills_required],
    skills_optional: [...filters.skills_optional],
    disciplines: [...filters.disciplines],
  }
}

// ---------- URL <-> filters ----------

function firstValue(raw: LocationQuery[string] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value : ''
}

function splitList(raw: LocationQuery[string] | undefined): string[] {
  return firstValue(raw)
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part !== '')
}

/** Keep only allowed values, in the canonical order of the dictionary, without repeats. */
function enumList<T extends string>(raw: LocationQuery[string] | undefined, order: readonly T[]): T[] {
  const wanted = new Set(splitList(raw))
  return order.filter((value) => wanted.has(value))
}

function skillList(raw: LocationQuery[string] | undefined, known: ReadonlySet<string> | null): string[] {
  const result: string[] = []
  for (const part of splitList(raw)) {
    const id = part.toLowerCase()
    if (!SKILL_ID_PATTERN.test(id) || result.includes(id)) {
      continue
    }
    // With a loaded dictionary an unknown id would turn the whole search into a 422: drop it quietly.
    if (known !== null && !known.has(id)) {
      continue
    }
    result.push(id)
    if (result.length >= MAX_SKILLS) {
      break
    }
  }
  return result
}

function flag(raw: LocationQuery[string] | undefined): boolean {
  const value = firstValue(raw)
  return value === '1' || value === 'true'
}

function positiveInt(raw: LocationQuery[string] | undefined, max: number): number | null {
  const value = firstValue(raw)
  if (!/^\d{1,12}$/.test(value)) {
    return null
  }
  const parsed = Number(value)
  return parsed > 0 && parsed <= max ? parsed : null
}

/** Read filters from the address bar. Unknown or malformed values are dropped, never thrown. */
export function filtersFromQuery(query: LocationQuery, knownSkills: ReadonlySet<string> | null = null): SearchFilters {
  const required = skillList(query.skills_required, knownSkills)
  const optional = skillList(query.skills_optional, knownSkills).filter((id) => !required.includes(id))
  const city = firstValue(query.city).trim().slice(0, MAX_CITY_LENGTH)
  return {
    stacks: enumList(query.stacks, STACK_ORDER),
    grades: enumList(query.grades, GRADE_ORDER),
    team_roles: enumList(query.team_roles, TEAM_ROLE_ORDER),
    work_formats: enumList(query.work_formats, WORK_FORMAT_ORDER),
    city: city === '' ? null : city,
    skills_required: required,
    skills_optional: optional,
    strict_skills: flag(query.strict_skills),
    fsp_verified_only: flag(query.fsp_verified_only),
    confirmed_only: flag(query.confirmed_only),
    disciplines: enumList(query.disciplines, DISCIPLINE_ORDER),
    salary_max: positiveInt(query.salary_max, MAX_SALARY),
    text: firstValue(query.text).slice(0, TEXT_MAX_LENGTH),
    vacancy_id: positiveInt(query.vacancy_id, 2_147_483_647),
  }
}

/** Address-bar form of the filters; empty fields are left out so that links stay short and comparable. */
export function filtersToQuery(filters: SearchFilters): Record<string, string> {
  const query: Record<string, string> = {}
  const list = (key: string, values: readonly string[]): void => {
    if (values.length > 0) {
      query[key] = values.join(',')
    }
  }
  list('stacks', filters.stacks)
  list('grades', filters.grades)
  list('team_roles', filters.team_roles)
  list('work_formats', filters.work_formats)
  if (filters.city !== null && filters.city.trim() !== '') {
    query.city = filters.city.trim()
  }
  list('skills_required', filters.skills_required)
  list('skills_optional', filters.skills_optional)
  if (filters.strict_skills) query.strict_skills = '1'
  if (filters.fsp_verified_only) query.fsp_verified_only = '1'
  if (filters.confirmed_only) query.confirmed_only = '1'
  list('disciplines', filters.disciplines)
  if (filters.salary_max !== null) query.salary_max = String(filters.salary_max)
  if (filters.text.trim() !== '') query.text = filters.text.trim()
  if (filters.vacancy_id !== null) query.vacancy_id = String(filters.vacancy_id)
  return query
}

/** Stable string for comparing two sets of filters. `withText: false` ignores the free-text field. */
export function filtersKey(filters: SearchFilters, withText = true): string {
  return JSON.stringify(filtersToQuery(withText ? filters : { ...filters, text: '' }))
}

/** Link into the search page with some filters preset: `searchLocation({ stacks: ['backend'], grades: ['junior'] })`. */
export function searchLocation(preset: Partial<SearchFilters> = {}): RouteLocationRaw {
  const query: LocationQueryRaw = filtersToQuery({ ...emptyFilters(), ...preset })
  return { name: 'employer-search', query }
}

/** Number of filters that narrow the result (the free text and the vacancy are counted separately by the page). */
export function activeFilterCount(filters: SearchFilters): number {
  let count = 0
  count += filters.stacks.length
  count += filters.grades.length
  count += filters.team_roles.length
  count += filters.work_formats.length
  count += filters.city !== null ? 1 : 0
  count += filters.skills_required.length
  count += filters.skills_optional.length
  count += filters.strict_skills ? 1 : 0
  count += filters.fsp_verified_only ? 1 : 0
  count += filters.confirmed_only ? 1 : 0
  count += filters.disciplines.length
  count += filters.salary_max !== null ? 1 : 0
  count += filters.vacancy_id !== null ? 1 : 0
  return count
}

/** Request body for POST /employer/search: only the fields that are set. */
export function toMatchQuery(filters: SearchFilters, limit: number, offset: number): MatchQuery {
  const query: MatchQuery = { limit, offset }
  if (filters.stacks.length > 0) query.stacks = filters.stacks
  if (filters.grades.length > 0) query.grades = filters.grades
  if (filters.team_roles.length > 0) query.team_roles = filters.team_roles
  if (filters.work_formats.length > 0) query.work_formats = filters.work_formats
  if (filters.city !== null && filters.city.trim() !== '') query.city = filters.city.trim()
  if (filters.skills_required.length > 0) query.skills_required = filters.skills_required
  if (filters.skills_optional.length > 0) query.skills_optional = filters.skills_optional
  // Also meaningful without own required skills: the vacancy may bring some.
  if (filters.strict_skills) query.strict_skills = true
  if (filters.fsp_verified_only) query.fsp_verified_only = true
  if (filters.confirmed_only) query.confirmed_only = true
  if (filters.disciplines.length > 0) query.disciplines = filters.disciplines
  if (filters.salary_max !== null) query.salary_max = filters.salary_max
  if (filters.text.trim() !== '') query.text = filters.text.trim()
  if (filters.vacancy_id !== null) query.vacancy_id = filters.vacancy_id
  return query
}
