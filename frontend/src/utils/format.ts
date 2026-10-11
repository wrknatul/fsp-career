// Formatting helpers: money, dates, plurals, time left. All output is Russian.

const NBSP = ' '
const MINUS = '−'

const numberFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const decimalFormat = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
] as const

// ---------- Plurals ----------

export type PluralForms = readonly [one: string, few: string, many: string]

/** Word form for a count: plural(5, ['год', 'года', 'лет']) -> 'лет'. Fractions take the "few" form (1,5 года). */
export function plural(n: number, forms: PluralForms): string {
  if (!Number.isInteger(n)) {
    return forms[1]
  }
  const abs = Math.abs(n)
  const lastTwo = abs % 100
  const last = abs % 10
  if (lastTwo >= 11 && lastTwo <= 14) {
    return forms[2]
  }
  if (last === 1) {
    return forms[0]
  }
  if (last >= 2 && last <= 4) {
    return forms[1]
  }
  return forms[2]
}

/** Count with its noun: formatCount(3, ['кандидат', 'кандидата', 'кандидатов']) -> '3 кандидата'. */
export function formatCount(n: number, forms: PluralForms): string {
  return `${formatNumber(n)}${NBSP}${plural(n, forms)}`
}

// ---------- Numbers and money ----------

/** 120000 -> '120 000' (non-breaking spaces). */
export function formatNumber(n: number): string {
  return numberFormat.format(n)
}

/** 12.34 -> '12,3'. */
export function formatDecimal(n: number): string {
  return decimalFormat.format(n)
}

/** 120000 -> '120 000 ₽' */
export function formatMoney(amount: number): string {
  return `${numberFormat.format(Math.round(amount))}${NBSP}₽`
}

/**
 * Vacancy salary range: '120 000 – 200 000 ₽', 'от 120 000 ₽', 'до 200 000 ₽'.
 * Returns `emptyText` when neither bound is set.
 */
export function formatMoneyRange(from: number | null | undefined, to: number | null | undefined, emptyText = 'Не указана'): string {
  const hasFrom = typeof from === 'number'
  const hasTo = typeof to === 'number'
  if (hasFrom && hasTo) {
    if (from === to) {
      return formatMoney(from)
    }
    return `${numberFormat.format(from)}${NBSP}–${NBSP}${formatMoney(to)}`
  }
  if (hasFrom) {
    return `от${NBSP}${formatMoney(from)}`
  }
  if (hasTo) {
    return `до${NBSP}${formatMoney(to)}`
  }
  return emptyText
}

/** 0.256 -> '26%' */
export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`
}

/** Signed one-decimal points with a real minus sign: 12 -> '+12,0', -8 -> '−8,0'. */
export function formatPoints(points: number): string {
  const rounded = Math.round(points * 10) / 10
  if (rounded < 0) {
    return `${MINUS}${decimalFormat.format(Math.abs(rounded))}`
  }
  return `${rounded > 0 ? '+' : ''}${decimalFormat.format(rounded)}`
}

/** Unsigned one-decimal score: 46.8 -> '46,8'. */
export function formatScore(score: number): string {
  return decimalFormat.format(score)
}

/** Years of experience: 1 -> '1 год', 1.5 -> '1,5 года', 5 -> '5 лет'. */
export function formatYears(years: number): string {
  const rounded = Math.round(years * 10) / 10
  const text = Number.isInteger(rounded) ? String(rounded) : String(rounded).replace('.', ',')
  return `${text}${NBSP}${plural(rounded, ['год', 'года', 'лет'])}`
}

// ---------- Dates ----------

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/
const HAS_ZONE = /(?:Z|[+-]\d{2}:?\d{2})$/i

/**
 * Parse a server date. 'YYYY-MM-DD' becomes a local date (no timezone shift);
 * date-times without an explicit zone are treated as UTC (the contract says UTC).
 * Returns null for anything unparsable.
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (typeof value !== 'string' || value === '') {
    return null
  }
  const dateOnly = DATE_ONLY.exec(value)
  if (dateOnly !== null) {
    const date = new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    return Number.isNaN(date.getTime()) ? null : date
  }
  const normalized = HAS_ZONE.test(value) || !value.includes('T') ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

/** '2026-05-14' -> '14 мая 2026'. Returns '—' for empty or invalid input. */
export function formatDate(value: string | null | undefined): string {
  const date = parseServerDate(value)
  if (date === null) {
    return '—'
  }
  return `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]} ${date.getFullYear()}`
}

/** '2026-05-14' -> '14 мая' (no year). */
export function formatDayMonth(value: string | null | undefined): string {
  const date = parseServerDate(value)
  if (date === null) {
    return '—'
  }
  return `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]}`
}

/** '2026-05-14' -> '14.05.2026'. */
export function formatShortDate(value: string | null | undefined): string {
  const date = parseServerDate(value)
  if (date === null) {
    return '—'
  }
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}

/** ISO date-time -> '14 мая 2026, 15:30' in the browser's time zone. */
export function formatDateTime(value: string | null | undefined): string {
  const date = parseServerDate(value)
  if (date === null) {
    return '—'
  }
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${formatDate(value)}, ${hours}:${minutes}`
}

// ---------- Relative time ----------

/**
 * Time left until `target` as words: 'меньше минуты', '12 мин', '2 ч 10 мин', '3 дня'.
 * Returns 'сейчас' when the target is already in the past.
 */
export function formatTimeLeft(target: string | Date | null | undefined, nowMs: number = Date.now()): string {
  const date = target instanceof Date ? target : parseServerDate(target)
  if (date === null) {
    return '—'
  }
  const leftMs = date.getTime() - nowMs
  if (leftMs <= 0) {
    return 'сейчас'
  }
  const minutes = Math.ceil(leftMs / 60_000)
  if (minutes < 2 && leftMs < 60_000) {
    return 'меньше минуты'
  }
  if (minutes < 60) {
    return `${minutes}${NBSP}мин`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    const rest = minutes % 60
    return rest === 0 ? `${hours}${NBSP}ч` : `${hours}${NBSP}ч ${rest}${NBSP}мин`
  }
  const days = Math.ceil(hours / 24)
  return `${days}${NBSP}${plural(days, ['день', 'дня', 'дней'])}`
}

/** How long ago: 'только что', '5 мин назад', '3 ч назад', 'вчера', '4 дня назад', then a date. */
export function formatAgo(value: string | null | undefined, nowMs: number = Date.now()): string {
  const date = parseServerDate(value)
  if (date === null) {
    return '—'
  }
  const diffMs = nowMs - date.getTime()
  if (diffMs < 60_000) {
    return 'только что'
  }
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 60) {
    return `${minutes}${NBSP}мин назад`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours}${NBSP}ч назад`
  }
  const days = Math.floor(hours / 24)
  if (days === 1) {
    return 'вчера'
  }
  if (days < 7) {
    return `${days}${NBSP}${plural(days, ['день', 'дня', 'дней'])} назад`
  }
  return formatDate(value)
}

/** Countdown for a timer: 452 -> '7:32', 3725 -> '1:02:05'. Negative values clamp to '0:00'. */
export function formatCountdown(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  const ss = String(seconds).padStart(2, '0')
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${ss}`
  }
  return `${minutes}:${ss}`
}
