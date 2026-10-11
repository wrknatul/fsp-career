import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getErrorMessage } from '@/api/client'
import { getDictionaries } from '@/api/reference'
import type {
  CompetitionLevel,
  Dictionaries,
  Discipline,
  Grade,
  Source,
  SportRank,
  Stack,
  TeamRole,
  Verification,
  WorkFormat,
} from '@/api/types'
import {
  COMPETITION_LEVEL_ORDER,
  COMPETITION_LEVEL_TITLES,
  DISCIPLINE_ORDER,
  DISCIPLINE_TITLES,
  GRADE_ORDER,
  GRADE_TITLES,
  SOURCE_TITLES,
  SPORT_RANK_ORDER,
  SPORT_RANK_TITLES,
  STACK_ORDER,
  STACK_TITLES,
  TEAM_ROLE_ORDER,
  TEAM_ROLE_TITLES,
  VERIFICATION_TITLES,
  WORK_FORMAT_ORDER,
  WORK_FORMAT_TITLES,
  optionsFrom,
  type SelectOption,
} from '@/utils/labels'

export type ReferenceStatus = 'idle' | 'loading' | 'ready' | 'error'

type Titled<T extends string> = { id: T; title: string }

/** Title by id: server dictionary first, then the static caption, then the raw id. */
function titleOf<T extends string>(
  list: readonly Titled<T>[] | undefined,
  fallback: Record<T, string>,
  id: T | null | undefined,
): string {
  if (id === null || id === undefined) {
    return '—'
  }
  const found = list?.find((item) => item.id === id)
  return found?.title ?? fallback[id] ?? id
}

/** Options in canonical order; titles from the server when available. */
function optionsOf<T extends string>(
  list: readonly Titled<T>[] | undefined,
  order: readonly T[],
  fallback: Record<T, string>,
): SelectOption<T>[] {
  if (list === undefined || list.length === 0) {
    return optionsFrom(order, fallback)
  }
  return list.map((item) => ({ value: item.id, label: item.title }))
}

export const useReferenceStore = defineStore('reference', () => {
  const dictionaries = ref<Dictionaries | null>(null)
  const status = ref<ReferenceStatus>('idle')
  const error = ref('')
  let loadPromise: Promise<void> | null = null

  const ready = computed(() => status.value === 'ready')
  /** 'mock' while the FSP registry is simulated; drives the demo banner and the "демо" badge mark. */
  const registryMode = computed(() => dictionaries.value?.fsp_registry_mode ?? null)
  const isMock = computed(() => registryMode.value === 'mock')

  /**
   * Load dictionaries once. Never throws: on failure `status` is 'error' and the next call retries.
   * Await it before rendering anything that needs skills or cities.
   */
  function load(force = false): Promise<void> {
    if (!force && status.value === 'ready') {
      return Promise.resolve()
    }
    if (loadPromise !== null) {
      return loadPromise
    }
    status.value = 'loading'
    error.value = ''
    loadPromise = getDictionaries()
      .then((data) => {
        dictionaries.value = data
        status.value = 'ready'
      })
      .catch((err: unknown) => {
        error.value = getErrorMessage(err)
        status.value = 'error'
      })
      .finally(() => {
        loadPromise = null
      })
    return loadPromise
  }

  // ---------- Titles by id (safe before the dictionaries arrive) ----------

  const stackTitle = (id: Stack | null | undefined): string => titleOf(dictionaries.value?.stacks, STACK_TITLES, id)
  const gradeTitle = (id: Grade | null | undefined): string => titleOf(dictionaries.value?.grades, GRADE_TITLES, id)
  const teamRoleTitle = (id: TeamRole | null | undefined): string =>
    titleOf(dictionaries.value?.team_roles, TEAM_ROLE_TITLES, id)
  const workFormatTitle = (id: WorkFormat | null | undefined): string =>
    titleOf(dictionaries.value?.work_formats, WORK_FORMAT_TITLES, id)
  const sourceTitle = (id: Source | null | undefined): string => titleOf(dictionaries.value?.sources, SOURCE_TITLES, id)
  const verificationTitle = (id: Verification | null | undefined): string =>
    titleOf(dictionaries.value?.verifications, VERIFICATION_TITLES, id)
  const disciplineTitle = (id: Discipline | null | undefined): string =>
    titleOf(dictionaries.value?.disciplines, DISCIPLINE_TITLES, id)
  /** Competition level ('national' -> 'Всероссийский'). */
  const levelTitle = (id: CompetitionLevel | null | undefined): string =>
    titleOf(dictionaries.value?.competition_levels, COMPETITION_LEVEL_TITLES, id)
  /** Sport rank ('kms' -> 'КМС'). */
  const rankTitle = (id: SportRank | null | undefined): string =>
    titleOf(dictionaries.value?.sport_ranks, SPORT_RANK_TITLES, id)

  /** Skill caption; unknown ids come back as-is. */
  function skillTitle(id: string | null | undefined): string {
    if (id === null || id === undefined) {
      return '—'
    }
    return dictionaries.value?.skills.find((skill) => skill.id === id)?.title ?? id
  }

  /** Join captions of a list: joinTitles(category.work_formats, reference.workFormatTitle) -> 'Удалённо, Гибрид'. */
  function joinTitles<T>(ids: readonly T[], titleFn: (id: T) => string, separator = ', '): string {
    return ids.map(titleFn).join(separator)
  }

  // ---------- Options for selects / chip groups ----------

  const stackOptions = computed(() => optionsOf(dictionaries.value?.stacks, STACK_ORDER, STACK_TITLES))
  const gradeOptions = computed(() => optionsOf(dictionaries.value?.grades, GRADE_ORDER, GRADE_TITLES))
  const teamRoleOptions = computed(() => optionsOf(dictionaries.value?.team_roles, TEAM_ROLE_ORDER, TEAM_ROLE_TITLES))
  const workFormatOptions = computed(() =>
    optionsOf(dictionaries.value?.work_formats, WORK_FORMAT_ORDER, WORK_FORMAT_TITLES),
  )
  const disciplineOptions = computed(() =>
    optionsOf(dictionaries.value?.disciplines, DISCIPLINE_ORDER, DISCIPLINE_TITLES),
  )
  const levelOptions = computed(() =>
    optionsOf(dictionaries.value?.competition_levels, COMPETITION_LEVEL_ORDER, COMPETITION_LEVEL_TITLES),
  )
  const rankOptions = computed(() => optionsOf(dictionaries.value?.sport_ranks, SPORT_RANK_ORDER, SPORT_RANK_TITLES))
  /** Skills sorted by caption: { value: id, label: title }. Empty until the dictionaries are loaded. */
  const skillOptions = computed<SelectOption[]>(() =>
    (dictionaries.value?.skills ?? [])
      .map((skill) => ({ value: skill.id, label: skill.title }))
      .sort((a, b) => a.label.localeCompare(b.label, 'ru')),
  )
  const cities = computed<string[]>(() => dictionaries.value?.cities ?? [])
  const cityOptions = computed<SelectOption[]>(() => cities.value.map((city) => ({ value: city, label: city })))

  return {
    dictionaries,
    status,
    error,
    ready,
    registryMode,
    isMock,
    load,
    stackTitle,
    gradeTitle,
    teamRoleTitle,
    workFormatTitle,
    sourceTitle,
    verificationTitle,
    disciplineTitle,
    levelTitle,
    rankTitle,
    skillTitle,
    joinTitles,
    stackOptions,
    gradeOptions,
    teamRoleOptions,
    workFormatOptions,
    disciplineOptions,
    levelOptions,
    rankOptions,
    skillOptions,
    cities,
    cityOptions,
  }
})
