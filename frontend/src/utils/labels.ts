// Static Russian captions for contract literals (SPEC section 4).
// The reference store prefers the server dictionaries and falls back to these,
// so captions never disappear when /reference/dictionaries is slow or down.

import type {
  AchievementResult,
  CompetitionLevel,
  Discipline,
  Grade,
  OfferStatus,
  Source,
  SportRank,
  Stack,
  TeamRole,
  Verification,
  WorkFormat,
} from '@/api/types'

export const STACK_TITLES: Record<Stack, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  fullstack: 'Fullstack',
  mobile: 'Мобильная разработка',
  ml: 'ML / Data Science',
  devops: 'DevOps / SRE',
  security: 'Информационная безопасность',
  embedded: 'Embedded / робототехника',
  qa: 'Тестирование',
  analyst: 'Аналитика',
}

export const GRADE_TITLES: Record<Grade, string> = {
  intern: 'Стажёр',
  junior: 'Junior',
  middle: 'Middle',
  senior: 'Senior',
}

export const TEAM_ROLE_TITLES: Record<TeamRole, string> = {
  lead: 'Тимлид',
  developer: 'Разработчик',
  researcher: 'Исследователь / алгоритмист',
  devops: 'Инженер инфраструктуры',
  qa: 'Тестировщик',
  analyst: 'Аналитик',
}

export const WORK_FORMAT_TITLES: Record<WorkFormat, string> = {
  remote: 'Удалённо',
  office: 'Офис',
  hybrid: 'Гибрид',
}

export const SOURCE_TITLES: Record<Source, string> = {
  fsp: 'Реестр ФСП',
  test: 'Тест платформы',
  resume: 'Резюме',
  self: 'Указано соискателем',
}

export const VERIFICATION_TITLES: Record<Verification, string> = {
  verified: 'Подтверждено ФСП',
  tested: 'Подтверждено тестом',
  parsed: 'Из резюме',
  declared: 'Заявлено',
}

/** Trust weight of a confirmation level (SPEC section 4). */
export const VERIFICATION_WEIGHTS: Record<Verification, number> = {
  verified: 1,
  tested: 0.85,
  parsed: 0.55,
  declared: 0.35,
}

export const DISCIPLINE_TITLES: Record<Discipline, string> = {
  algorithmic: 'Алгоритмическое программирование',
  product: 'Продуктовое программирование (хакатон)',
  security: 'Программирование систем информационной безопасности',
  robotics: 'Программирование робототехники',
  uav: 'Программирование БАС',
}

export const COMPETITION_LEVEL_TITLES: Record<CompetitionLevel, string> = {
  municipal: 'Муниципальный',
  regional: 'Региональный',
  district: 'Федеральный округ',
  national: 'Всероссийский',
  international: 'Международный',
}

export const SPORT_RANK_TITLES: Record<SportRank, string> = {
  third: 'III разряд',
  second: 'II разряд',
  first: 'I разряд',
  kms: 'КМС',
  ms: 'Мастер спорта России',
}

export const ACHIEVEMENT_RESULT_TITLES: Record<AchievementResult, string> = {
  winner: 'Победитель',
  prize: 'Призёр',
  participant: 'Участник',
}

export const OFFER_STATUS_TITLES: Record<OfferStatus, string> = {
  sent: 'Ждёт ответа',
  accepted: 'Принят',
  declined: 'Отклонён',
}

/** Quiz level 0..3 as returned in TestResult.level / level_title. */
export const QUIZ_LEVEL_TITLES: Record<0 | 1 | 2 | 3, string> = {
  0: 'Не сдан',
  1: 'Базовый',
  2: 'Уверенный',
  3: 'Продвинутый',
}

// Canonical orders (dictionary order of SPEC section 4): use them to lay out matrices and filters.
export const STACK_ORDER: readonly Stack[] = [
  'backend',
  'frontend',
  'fullstack',
  'mobile',
  'ml',
  'devops',
  'security',
  'embedded',
  'qa',
  'analyst',
]
export const GRADE_ORDER: readonly Grade[] = ['intern', 'junior', 'middle', 'senior']
export const TEAM_ROLE_ORDER: readonly TeamRole[] = ['lead', 'developer', 'researcher', 'devops', 'qa', 'analyst']
export const WORK_FORMAT_ORDER: readonly WorkFormat[] = ['remote', 'hybrid', 'office']
export const DISCIPLINE_ORDER: readonly Discipline[] = ['algorithmic', 'product', 'security', 'robotics', 'uav']
export const COMPETITION_LEVEL_ORDER: readonly CompetitionLevel[] = [
  'municipal',
  'regional',
  'district',
  'national',
  'international',
]
export const SPORT_RANK_ORDER: readonly SportRank[] = ['third', 'second', 'first', 'kms', 'ms']

export type SelectOption<T extends string | number = string> = { value: T; label: string }

/** Build select/chip options from a title map in a given order. */
export function optionsFrom<T extends string>(order: readonly T[], titles: Record<T, string>): SelectOption<T>[] {
  return order.map((value) => ({ value, label: titles[value] }))
}
