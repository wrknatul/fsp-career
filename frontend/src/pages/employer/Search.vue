<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '@/api/client'
import { listVacancies, searchCandidates } from '@/api/employer'
import type { CandidateMatch, SearchResponse } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppTextarea from '@/components/AppTextarea.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { formatCount, formatMoney } from '@/utils/format'

import MatchCard from './components/MatchCard.vue'
import SearchFilterPanel from './components/SearchFilterPanel.vue'
import VerificationLegend from './components/VerificationLegend.vue'
import {
  TEXT_MAX_LENGTH,
  activeFilterCount,
  cloneFilters,
  emptyFilters,
  filtersFromQuery,
  filtersKey,
  filtersToQuery,
  toMatchQuery,
  type SearchFilters,
} from './searchFilters'

// Search for candidates. All filters live in the address bar (a link can be shared, "back" works);
// the page keeps a draft of them and applies it with a short delay (chips, lists) or on "Найти" (free text).

const PAGE_SIZE = 20
/** The server accepts `limit` up to 50. */
const MAX_PAGE_LIMIT = 50
/** The server accepts offset up to 500. */
const MAX_OFFSET = 500
/** sessionStorage key: how many cards of the last search were on screen (to restore them on "back"). */
const LOADED_KEY = 'fsp.employer.search.loaded'
const COMMIT_DELAY_MS = 450
const CANDIDATES = ['кандидат', 'кандидата', 'кандидатов'] as const

const route = useRoute()
const router = useRouter()
const reference = useReferenceStore()
const toast = useToastStore()

const knownSkills = computed<ReadonlySet<string> | null>(() =>
  reference.skillOptions.length > 0 ? new Set(reference.skillOptions.map((option) => option.value)) : null,
)

function parseRoute(): SearchFilters {
  return filtersFromQuery(route.query, knownSkills.value)
}

/** What the address bar says right now (and what the results on screen were requested with). */
const applied = ref<SearchFilters>(parseRoute())
/** What the form shows: ahead of `applied` by a moment. */
const draft = ref<SearchFilters>(cloneFilters(applied.value))

// ---------- Own vacancies (for "подобрать под вакансию") ----------

const { data: vacancies, status: vacanciesStatus } = useLoader(() => listVacancies())
const vacancyList = computed(() => vacancies.value ?? [])
const appliedVacancy = computed(() => vacancyList.value.find((vacancy) => vacancy.id === applied.value.vacancy_id) ?? null)

// ---------- Results ----------

type Phase = 'loading' | 'ready' | 'error'

const phase = ref<Phase>('loading')
const errorMessage = ref('')
const response = shallowRef<SearchResponse | null>(null)
const items = shallowRef<CandidateMatch[]>([])
const loadingMore = ref(false)
let runId = 0

type LoadedMemo = { path: string; count: number }

function readLoadedMemo(): LoadedMemo | null {
  try {
    const raw: unknown = JSON.parse(window.sessionStorage.getItem(LOADED_KEY) ?? 'null')
    if (
      typeof raw === 'object' &&
      raw !== null &&
      'path' in raw &&
      'count' in raw &&
      typeof raw.path === 'string' &&
      typeof raw.count === 'number'
    ) {
      return { path: raw.path, count: raw.count }
    }
  } catch {
    // Blocked or broken storage: the search simply starts from the first page.
  }
  return null
}

/** Remember how many cards the current search shows, so that "back" from a candidate card brings them all back. */
function rememberLoaded(): void {
  try {
    const memo: LoadedMemo = { path: route.fullPath, count: items.value.length }
    window.sessionStorage.setItem(LOADED_KEY, JSON.stringify(memo))
  } catch {
    // Storage is only a convenience.
  }
}

/** The scroll position Vue Router stored for this history entry; present only when we came here by "back". */
function savedScrollTop(): number | null {
  const scroll: unknown = router.options.history.state.scroll
  if (typeof scroll === 'object' && scroll !== null && 'top' in scroll && typeof scroll.top === 'number') {
    return scroll.top
  }
  return null
}

/**
 * `want` is how many cards to show after the run: one page normally, more when the page is restored by "back".
 * The server gives at most 50 per request, so a bigger restore takes several requests.
 */
async function runSearch(want: number = PAGE_SIZE): Promise<void> {
  runId += 1
  const current = runId
  phase.value = 'loading'
  errorMessage.value = ''
  try {
    const target = Math.min(Math.max(want, PAGE_SIZE), MAX_OFFSET)
    const result = await searchCandidates(toMatchQuery(applied.value, Math.min(target, MAX_PAGE_LIMIT), 0))
    if (current !== runId) {
      return
    }
    let collected = result.items
    while (collected.length < Math.min(target, result.total)) {
      const limit = Math.min(MAX_PAGE_LIMIT, target - collected.length)
      const next = await searchCandidates(toMatchQuery(applied.value, limit, collected.length))
      if (current !== runId) {
        return
      }
      const known = new Set(collected.map((item) => item.candidate.id))
      const fresh = next.items.filter((item) => !known.has(item.candidate.id))
      if (fresh.length === 0) {
        break
      }
      collected = [...collected, ...fresh]
    }
    response.value = { ...result, items: collected }
    items.value = collected
    phase.value = 'ready'
    rememberLoaded()
  } catch (err) {
    if (current !== runId) {
      return
    }
    errorMessage.value = getErrorMessage(err)
    phase.value = 'error'
  }
}

const total = computed(() => response.value?.total ?? 0)
const canLoadMore = computed(() => items.value.length < total.value && items.value.length <= MAX_OFFSET)

async function loadMore(): Promise<void> {
  if (response.value === null || loadingMore.value) {
    return
  }
  const current = runId
  loadingMore.value = true
  try {
    const next = await searchCandidates(toMatchQuery(applied.value, PAGE_SIZE, items.value.length))
    if (current !== runId) {
      return
    }
    const known = new Set(items.value.map((item) => item.candidate.id))
    items.value = [...items.value, ...next.items.filter((item) => !known.has(item.candidate.id))]
    response.value = { ...next, items: items.value }
    rememberLoaded()
  } catch (err) {
    toast.fromError(err)
  } finally {
    loadingMore.value = false
  }
}

const hasScores = computed(() => items.value.some((item) => item.score !== null))
const isRefreshing = computed(() => phase.value === 'loading' && response.value !== null)

// ---------- Applying filters ----------

let commitTimer: number | null = null

function clearCommitTimer(): void {
  if (commitTimer !== null) {
    window.clearTimeout(commitTimer)
    commitTimer = null
  }
}

function sameAsApplied(): boolean {
  return JSON.stringify(filtersToQuery(draft.value)) === JSON.stringify(filtersToQuery(applied.value))
}

/** Put the draft into the address bar (a new history entry); returns false when nothing changed. */
function commit(): boolean {
  clearCommitTimer()
  if (sameAsApplied()) {
    return false
  }
  void router.push({ name: 'employer-search', query: filtersToQuery(draft.value) })
  return true
}

function patch(change: Partial<SearchFilters>): void {
  draft.value = { ...draft.value, ...change }
}

function patchAndCommit(change: Partial<SearchFilters>): void {
  patch(change)
  commit()
}

/** Explicit "Найти": also repeats the search when nothing changed. */
function submit(): void {
  filtersOpen.value = false
  if (!commit()) {
    void runSearch()
  }
}

function resetFilters(): void {
  patchAndCommit({ ...emptyFilters(), text: draft.value.text })
}

// Text is committed explicitly, everything else with a delay, so that a row of clicks makes one request.
watch(
  () => filtersKey(draft.value, false),
  () => {
    clearCommitTimer()
    commitTimer = window.setTimeout(() => {
      commitTimer = null
      commit()
    }, COMMIT_DELAY_MS)
  },
)

// The address bar changed (a commit, "back", a link from another page): follow it.
watch(
  () => route.fullPath,
  () => {
    if (route.name !== 'employer-search') {
      return
    }
    const next = parseRoute()
    applied.value = next
    if (filtersKey(next) !== filtersKey(draft.value)) {
      draft.value = cloneFilters(next)
    }
    void runSearch()
  },
)

// First run. When the page is opened by "back" (the history entry has a saved scroll position), bring back
// the cards that were on screen and the scroll position: the router restored the scroll before they loaded.
const returnScrollTop = savedScrollTop()
const returnMemo = returnScrollTop === null ? null : readLoadedMemo()
const returnCount = returnMemo !== null && returnMemo.path === route.fullPath ? returnMemo.count : PAGE_SIZE
let mounted = true

void runSearch(returnCount).then(async () => {
  if (returnScrollTop === null || returnScrollTop <= 0 || phase.value !== 'ready') {
    return
  }
  await nextTick()
  // The user may have left the page while the cards were loading: never scroll another page.
  if (mounted && window.scrollY < returnScrollTop) {
    window.scrollTo({ top: returnScrollTop, behavior: 'instant' })
  }
})

onBeforeUnmount(() => {
  mounted = false
  clearCommitTimer()
  unlockScroll()
})

// ---------- Summary chips of the applied filters ----------

type Chip = { key: string; label: string; remove: () => void }

function without<T>(list: readonly T[], value: T): T[] {
  return list.filter((item) => item !== value)
}

const chips = computed<Chip[]>(() => {
  const filters = applied.value
  const list: Chip[] = []
  if (filters.vacancy_id !== null) {
    const title = appliedVacancy.value?.title ?? `№${filters.vacancy_id}`
    list.push({ key: 'vacancy', label: `Вакансия: ${title}`, remove: () => patchAndCommit({ vacancy_id: null }) })
  }
  for (const stack of filters.stacks) {
    list.push({ key: `stack:${stack}`, label: reference.stackTitle(stack), remove: () => patchAndCommit({ stacks: without(filters.stacks, stack) }) })
  }
  for (const grade of filters.grades) {
    list.push({ key: `grade:${grade}`, label: reference.gradeTitle(grade), remove: () => patchAndCommit({ grades: without(filters.grades, grade) }) })
  }
  for (const role of filters.team_roles) {
    list.push({ key: `role:${role}`, label: reference.teamRoleTitle(role), remove: () => patchAndCommit({ team_roles: without(filters.team_roles, role) }) })
  }
  for (const format of filters.work_formats) {
    list.push({ key: `format:${format}`, label: reference.workFormatTitle(format), remove: () => patchAndCommit({ work_formats: without(filters.work_formats, format) }) })
  }
  if (filters.city !== null) {
    list.push({ key: 'city', label: `Город: ${filters.city}`, remove: () => patchAndCommit({ city: null }) })
  }
  for (const skill of filters.skills_required) {
    list.push({ key: `req:${skill}`, label: `Нужен ${reference.skillTitle(skill)}`, remove: () => patchAndCommit({ skills_required: without(filters.skills_required, skill) }) })
  }
  for (const skill of filters.skills_optional) {
    list.push({ key: `opt:${skill}`, label: `Желательно ${reference.skillTitle(skill)}`, remove: () => patchAndCommit({ skills_optional: without(filters.skills_optional, skill) }) })
  }
  if (filters.strict_skills) {
    list.push({ key: 'strict', label: 'Все обязательные навыки', remove: () => patchAndCommit({ strict_skills: false }) })
  }
  if (filters.fsp_verified_only) {
    list.push({ key: 'fsp', label: 'Только с результатами ФСП', remove: () => patchAndCommit({ fsp_verified_only: false }) })
  }
  if (filters.confirmed_only) {
    list.push({ key: 'confirmed', label: 'Только с подтверждением', remove: () => patchAndCommit({ confirmed_only: false }) })
  }
  for (const discipline of filters.disciplines) {
    list.push({ key: `disc:${discipline}`, label: reference.disciplineTitle(discipline), remove: () => patchAndCommit({ disciplines: without(filters.disciplines, discipline) }) })
  }
  if (filters.salary_max !== null) {
    list.push({ key: 'salary', label: `Бюджет до ${formatMoney(filters.salary_max)}`, remove: () => patchAndCommit({ salary_max: null }) })
  }
  return list
})

const draftFilterCount = computed(() => activeFilterCount(draft.value))

/**
 * What the chosen vacancy really contributes to the query. The backend takes a field from the vacancy only
 * when the request left it empty; skills are joined, and the vacancy title and description join the query text.
 */
const vacancyNote = computed(() => {
  const vacancy = appliedVacancy.value
  if (vacancy === null) {
    return ''
  }
  const filters = applied.value
  const taken: string[] = []
  if (filters.stacks.length === 0) {
    taken.push(`стек ${reference.stackTitle(vacancy.stack)}`)
  }
  if (filters.grades.length === 0) {
    taken.push(`грейд ${reference.gradeTitle(vacancy.grade)}`)
  }
  if (filters.team_roles.length === 0 && vacancy.team_role !== null) {
    taken.push(`роль ${reference.teamRoleTitle(vacancy.team_role)}`)
  }
  if (filters.work_formats.length === 0 && vacancy.work_formats.length > 0) {
    taken.push(`формат ${reference.joinTitles(vacancy.work_formats, reference.workFormatTitle)}`)
  }
  if (filters.city === null && vacancy.city) {
    taken.push(`город ${vacancy.city}`)
  }
  if (filters.salary_max === null && vacancy.salary_to !== null) {
    taken.push(`бюджет до ${formatMoney(vacancy.salary_to)}`)
  }
  const chosenByYou =
    filters.stacks.length > 0 ||
    filters.grades.length > 0 ||
    filters.team_roles.length > 0 ||
    filters.work_formats.length > 0 ||
    filters.city !== null ||
    filters.salary_max !== null

  const sentences: string[] = []
  if (taken.length > 0) {
    sentences.push(`из вакансии взяты ${taken.join(', ')}.`)
  } else {
    sentences.push('все параметры вы выбрали сами, из вакансии учтены только навыки и текст.')
  }
  if (chosenByYou && taken.length > 0) {
    sentences.push('То, что вы выбрали сами, вакансия не перекрывает.')
  }
  if (vacancy.skills_required.length + vacancy.skills_optional.length > 0) {
    sentences.push('Навыки вакансии добавлены к вашим.')
  }
  sentences.push('Название и описание вакансии идут в текст запроса, поэтому совпадение с текстом считается и при пустом поле.')
  return sentences.join(' ')
})

// ---------- What was recognised in the free text ----------

const parsed = computed(() => {
  const value = response.value?.parsed_query ?? null
  if (value === null || (value.skills.length === 0 && value.stack === null && value.grade === null)) {
    return null
  }
  return value
})

const canApplyParsedStack = computed(
  () => parsed.value?.stack != null && !applied.value.stacks.includes(parsed.value.stack),
)
const canApplyParsedGrade = computed(
  () => parsed.value?.grade != null && !applied.value.grades.includes(parsed.value.grade),
)

function applyParsedStack(): void {
  const stack = parsed.value?.stack
  if (stack != null) {
    patchAndCommit({ stacks: [...applied.value.stacks, stack] })
  }
}
function applyParsedGrade(): void {
  const grade = parsed.value?.grade
  if (grade != null) {
    patchAndCommit({ grades: [...applied.value.grades, grade] })
  }
}

// ---------- Filters drawer (phones) ----------

const filtersOpen = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
const openButton = ref<InstanceType<typeof AppButton> | null>(null)
let previousOverflow = ''
let scrollLocked = false

function lockScroll(): void {
  if (!scrollLocked) {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    scrollLocked = true
  }
}

function unlockScroll(): void {
  if (scrollLocked) {
    document.body.style.overflow = previousOverflow
    scrollLocked = false
  }
}

function onWindowKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && filtersOpen.value) {
    filtersOpen.value = false
  }
}

watch(filtersOpen, async (isOpen) => {
  if (isOpen) {
    window.addEventListener('keydown', onWindowKeydown)
    lockScroll()
    await nextTick()
    closeButton.value?.focus()
  } else {
    window.removeEventListener('keydown', onWindowKeydown)
    unlockScroll()
    const trigger = openButton.value?.$el
    if (trigger instanceof HTMLElement) {
      trigger.focus()
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKeydown)
})

const headline = computed(() => {
  if (phase.value === 'error') {
    return ''
  }
  return `Найдено ${formatCount(total.value, CANDIDATES)}`
})
</script>

<template>
  <PageHeader
    title="Поиск кандидатов"
    eyebrow="Работодатель"
    subtitle="Выберите категорию или опишите, кого ищете, и сразу смотрите, чем подтверждён каждый кандидат. Откликов ждать не нужно: оффер с зарплатой вы отправляете сами."
  />

  <div class="search">
    <Transition name="fade">
      <div v-if="filtersOpen" class="search__backdrop" aria-hidden="true" @click="filtersOpen = false"></div>
    </Transition>

    <aside id="search-filters" class="filters" :class="{ 'is-open': filtersOpen }" aria-label="Фильтры поиска">
      <div class="filters__bar">
        <h2 class="filters__title">
          Фильтры
          <span v-if="draftFilterCount > 0" class="filters__count num">{{ draftFilterCount }}</span>
        </h2>
        <button ref="closeButton" type="button" class="filters__close" aria-label="Закрыть фильтры" @click="filtersOpen = false">
          <AppIcon name="x" :size="20" />
        </button>
      </div>

      <div class="filters__body">
        <SearchFilterPanel
          :filters="draft"
          :vacancies="vacancyList"
          :vacancies-failed="vacanciesStatus === 'error'"
          @update="patch"
        />
      </div>

      <div class="filters__foot">
        <AppButton variant="ghost" size="sm" :disabled="draftFilterCount === 0" @click="resetFilters">
          Сбросить фильтры
        </AppButton>
        <AppButton class="filters__apply" size="sm" @click="submit">Показать результаты</AppButton>
      </div>
    </aside>

    <div class="results">
      <form class="query card" @submit.prevent="submit">
        <AppTextarea
          v-model="draft.text"
          label="Опишите, кого вы ищете"
          placeholder="Например: backend-разработчик на Python и FastAPI, нужен опыт с PostgreSQL, готов работать удалённо"
          :rows="3"
          :maxlength="TEXT_MAX_LENGTH"
          hint="Платформа найдёт в тексте навыки, стек и грейд и сравнит запрос с профилями. Это сходство слов, а не смысла, поэтому ключевые навыки лучше ещё и выбрать в фильтрах."
          @keydown.ctrl.enter.prevent="submit"
          @keydown.meta.enter.prevent="submit"
        />
        <div class="query__row">
          <AppButton type="submit">
            <AppIcon name="search" :size="18" />
            Найти
          </AppButton>
          <AppButton ref="openButton" class="query__filters" variant="secondary" aria-controls="search-filters" @click="filtersOpen = true">
            <AppIcon name="filter" :size="18" />
            Фильтры<span v-if="draftFilterCount > 0" class="query__badge num">{{ draftFilterCount }}</span>
          </AppButton>
          <span class="query__keys muted text-xs">Ctrl + Enter — быстрый запуск</span>
        </div>
      </form>

      <ul v-if="chips.length > 0" class="chips" aria-label="Применённые фильтры">
        <li v-for="chip in chips" :key="chip.key">
          <button type="button" class="chip" :aria-label="`Убрать: ${chip.label}`" @click="chip.remove()">
            <span class="chip__text">{{ chip.label }}</span>
            <AppIcon name="x" :size="14" />
          </button>
        </li>
        <li>
          <button type="button" class="chip-reset" @click="resetFilters">Сбросить всё</button>
        </li>
      </ul>

      <div v-if="appliedVacancy" class="callout callout--primary vacancy-note">
        <AppIcon name="info" :size="18" />
        <p>
          Подбор под вакансию <strong>«{{ appliedVacancy.title }}»</strong>: {{ vacancyNote }}
        </p>
      </div>

      <StateBlock v-if="phase === 'loading' && response === null" state="loading" title="Подбираем кандидатов…" />
      <StateBlock v-else-if="phase === 'error'" state="error" :text="errorMessage" @retry="runSearch()" />

      <template v-else>
        <div v-if="parsed" class="parsed callout callout--primary">
          <AppIcon name="spark" :size="18" />
          <div class="parsed__body">
            <p class="parsed__title">Распознано в тексте запроса</p>
            <ul class="parsed__parts">
              <li v-if="parsed.skills.length > 0" class="parsed__part">
                <span class="parsed__key">Навыки</span>
                {{ parsed.skills.map((skill) => reference.skillTitle(skill)).join(', ') }}
              </li>
              <li v-if="parsed.stack" class="parsed__part">
                <span class="parsed__key">Стек</span>
                {{ reference.stackTitle(parsed.stack) }}
                <button v-if="canApplyParsedStack" type="button" class="link-button" @click="applyParsedStack">
                  оставить только его
                </button>
              </li>
              <li v-if="parsed.grade" class="parsed__part">
                <span class="parsed__key">Грейд</span>
                {{ reference.gradeTitle(parsed.grade) }}
                <button v-if="canApplyParsedGrade" type="button" class="link-button" @click="applyParsedGrade">
                  оставить только его
                </button>
              </li>
            </ul>
            <p class="parsed__note">
              Навыки из текста учтены в оценке как желательные. Стек и грейд из текста — подсказка, выдачу они не сужают.
            </p>
          </div>
        </div>

        <header class="results__head">
          <p class="results__count" aria-live="polite">{{ headline }}</p>
          <p v-if="items.length > 0" class="results__sort">
            <template v-if="hasScores">Сначала те, кто лучше подходит под запрос.</template>
            <template v-else>Оценки нет: в запросе нет навыков и текста. Кандидаты отсортированы по опыту и достижениям.</template>
          </p>
        </header>

        <VerificationLegend v-if="items.length > 0" />

        <StateBlock v-if="items.length === 0 && isRefreshing" state="loading" title="Подбираем кандидатов…" />
        <StateBlock
          v-else-if="items.length === 0"
          state="empty"
          title="Подходящих кандидатов не нашлось"
          text="Попробуйте убрать часть фильтров: например, «Только с подтверждением» или строгие навыки. Или опишите запрос другими словами."
        >
          <template v-if="chips.length > 0" #action>
            <AppButton variant="secondary" @click="resetFilters">Сбросить фильтры</AppButton>
          </template>
        </StateBlock>

        <div v-else class="list" :class="{ 'is-refreshing': isRefreshing }" :aria-busy="isRefreshing">
          <MatchCard v-for="item in items" :key="item.candidate.id" :match="item" :vacancy-id="applied.vacancy_id" />
        </div>

        <div v-if="items.length > 0" class="more">
          <AppButton v-if="canLoadMore" variant="secondary" :loading="loadingMore" @click="loadMore">
            Показать ещё
          </AppButton>
          <p class="more__note muted text-sm">
            Показано <span class="num">{{ items.length }}</span> из <span class="num">{{ total }}</span>
            <template v-if="items.length < total && !canLoadMore">. Уточните фильтры, чтобы увидеть остальных.</template>
          </p>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.search {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-5);
  align-items: start;
}
.results {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}

/* ----- Free text ----- */
.query {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.query__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
}
.query__badge {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  color: #fff;
  font-size: 0.6875rem;
}
.query__keys {
  display: none;
}

/* ----- Applied filters ----- */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  list-style: none;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-height: 32px;
  padding: 3px 8px 3px 12px;
  border: 1px solid var(--c-primary-soft-2);
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-align: left;
}
.chip:hover {
  background: var(--c-primary-soft-2);
}
.chip__text {
  min-width: 0;
  overflow-wrap: anywhere;
}
.chip :deep(svg) {
  flex: none;
}
.chip-reset {
  min-height: 32px;
  padding: 3px 10px;
  border: 0;
  background: transparent;
  color: var(--c-text-muted);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.chip-reset:hover {
  color: var(--c-danger-text);
}

/* ----- Recognised text ----- */
.vacancy-note {
  align-items: flex-start;
  line-height: 1.5;
}
.vacancy-note :deep(svg) {
  flex: none;
  margin-top: 2px;
  color: var(--c-primary);
}
.parsed {
  align-items: flex-start;
}
.parsed :deep(svg) {
  flex: none;
  margin-top: 2px;
  color: var(--c-primary);
}
.parsed__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.5;
}
.parsed__title {
  font-weight: 600;
  color: var(--c-ink);
}
.parsed__parts {
  display: flex;
  flex-wrap: wrap;
  gap: 4px var(--sp-5);
  list-style: none;
}
.parsed__part {
  color: var(--c-text);
}
.parsed__key {
  margin-right: 4px;
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.parsed__note {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.link-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* ----- Results ----- */
.results__head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.results__count {
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--c-ink);
}
.results__sort {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  transition: opacity var(--t-base) var(--ease);
}
.list.is-refreshing {
  opacity: 0.5;
  pointer-events: none;
}
.more {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
}

/* ----- Filters: a drawer on phones, a sticky column on desktop ----- */
.search__backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-drawer) - 1);
  background: rgba(27, 28, 33, 0.5);
}
.filters {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: var(--z-drawer);
  display: flex;
  flex-direction: column;
  width: min(92vw, 400px);
  background: var(--c-surface);
  box-shadow: var(--shadow-lg);
  visibility: hidden;
  transform: translateX(-104%);
  transition:
    transform var(--t-base) var(--ease),
    visibility 0s linear var(--t-base);
}
.filters.is-open {
  visibility: visible;
  transform: none;
  transition-delay: 0s;
}
.filters__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--c-border);
}
.filters__title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-md);
}
.filters__count {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fs-xs);
}
.filters__close {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: var(--r-md);
  background: transparent;
  color: var(--c-text-muted);
}
.filters__close:hover {
  background: var(--c-neutral-soft);
  color: var(--c-ink);
}
.filters__body {
  flex: 1;
  min-height: 0;
  padding: var(--sp-5);
  overflow-y: auto;
  overscroll-behavior: contain;
}
.filters__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-5);
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}

@media (min-width: 640px) {
  .query__keys {
    display: inline;
  }
}

@media (min-width: 960px) {
  .search {
    grid-template-columns: 320px minmax(0, 1fr);
    gap: var(--sp-6);
  }
  .search__backdrop,
  .filters__close,
  .filters__apply,
  .query__filters {
    display: none;
  }
  .filters {
    position: sticky;
    inset: auto;
    top: 80px;
    z-index: auto;
    width: auto;
    max-height: calc(100vh - 96px);
    border: 1px solid var(--c-border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-sm);
    visibility: visible;
    transform: none;
    transition: none;
  }
  .filters__bar {
    padding: var(--sp-4) var(--sp-5) var(--sp-3);
    border-bottom: 0;
  }
}
</style>
