<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getCategoryMatrix } from '@/api/employer'
import type { Discipline, TeamRole, WorkFormat } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatTile from '@/components/StatTile.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { formatCount, formatPercent } from '@/utils/format'
import { TEAM_ROLE_ORDER, WORK_FORMAT_ORDER } from '@/utils/labels'

import HeatMatrix from './components/HeatMatrix.vue'
import SliceList, { type SliceItem } from './components/SliceList.vue'
import { searchLocation, type SearchFilters } from './searchFilters'

// Showcase of categories: the base of candidates laid out as "stack x grade" plus slices by team role,
// work format and FSP discipline. The role and the format also narrow the matrix itself
// (parameters team_role / work_format, kept in the address bar).

const route = useRoute()
const router = useRouter()
const reference = useReferenceStore()
const toast = useToastStore()

function pickOne<T extends string>(raw: unknown, allowed: readonly T[]): T | null {
  const value = Array.isArray(raw) ? raw[0] : raw
  return allowed.find((item) => item === value) ?? null
}

const roleFilter = computed<TeamRole | null>(() => pickOne(route.query.team_role, TEAM_ROLE_ORDER))
const formatFilter = computed<WorkFormat | null>(() => pickOne(route.query.work_format, WORK_FORMAT_ORDER))
const hasFilters = computed(() => roleFilter.value !== null || formatFilter.value !== null)

const {
  data: matrix,
  status,
  errorMessage,
  load,
} = useLoader(() => getCategoryMatrix({ team_role: roleFilter.value, work_format: formatFilter.value }))

watch([roleFilter, formatFilter], () => {
  void load()
})

// A failed refresh keeps the previous numbers on screen: tell about it with a toast.
watch(status, (next) => {
  if (next === 'error' && matrix.value !== null) {
    toast.error(errorMessage.value)
  }
})

const CANDIDATES = ['кандидат', 'кандидата', 'кандидатов'] as const

/** Filters that stay on when a click leads into the search. */
const carry = computed<Partial<SearchFilters>>(() => ({
  team_roles: roleFilter.value === null ? [] : [roleFilter.value],
  work_formats: formatFilter.value === null ? [] : [formatFilter.value],
}))

function setMatrixFilter(key: 'team_role' | 'work_format', value: string | null): void {
  const query = { ...route.query }
  if (value === null) {
    delete query[key]
  } else {
    query[key] = value
  }
  void router.replace({ query })
}

function resetFilters(): void {
  const query = { ...route.query }
  delete query.team_role
  delete query.work_format
  void router.replace({ query })
}

function toggleRole(key: string): void {
  setMatrixFilter('team_role', roleFilter.value === key ? null : key)
}
function toggleFormat(key: string): void {
  setMatrixFilter('work_format', formatFilter.value === key ? null : key)
}

const roleSlices = computed<SliceItem[]>(() => {
  const counts = new Map((matrix.value?.by_team_role ?? []).map((item) => [item.team_role, item.count]))
  return reference.teamRoleOptions.map((option) => ({
    key: option.value,
    label: option.label,
    // While a role is chosen the response only holds that role: the others have no number, not "0".
    count: roleFilter.value !== null && roleFilter.value !== option.value ? null : (counts.get(option.value) ?? 0),
    to: searchLocation({
      ...carry.value,
      team_roles: [option.value],
    }),
  }))
})

const formatSlices = computed<SliceItem[]>(() => {
  const counts = new Map((matrix.value?.by_work_format ?? []).map((item) => [item.work_format, item.count]))
  return reference.workFormatOptions.map((option) => ({
    key: option.value,
    label: option.label,
    count: formatFilter.value !== null && formatFilter.value !== option.value ? null : (counts.get(option.value) ?? 0),
    to: searchLocation({
      ...carry.value,
      work_formats: [option.value],
    }),
  }))
})

const disciplineSlices = computed<SliceItem[]>(() => {
  const counts = new Map((matrix.value?.by_discipline ?? []).map((item) => [item.discipline, item.count]))
  return reference.disciplineOptions.map((option) => {
    const discipline: Discipline = option.value
    return {
      key: discipline,
      label: option.label,
      count: counts.get(discipline) ?? 0,
      to: searchLocation({ ...carry.value, disciplines: [discipline] }),
    }
  })
})

const fspShare = computed(() => {
  const data = matrix.value
  if (data === null || data.total_candidates === 0) {
    return ''
  }
  return `${formatPercent(data.fsp_verified_total / data.total_candidates)} от всех`
})
</script>

<template>
  <PageHeader
    title="Витрина категорий"
    eyebrow="Работодатель"
    subtitle="Кандидатов не нужно ждать: платформа уже разложила их по категориям на основе подтверждаемого профиля. Выберите категорию, посмотрите, чем подтверждён каждый факт, и предложите оффер с зарплатой."
  >
    <template #actions>
      <AppButton variant="secondary" :to="{ name: 'employer-vacancies' }">Мои вакансии</AppButton>
      <AppButton :to="searchLocation(carry)">
        <AppIcon name="search" :size="18" />
        Перейти к поиску
      </AppButton>
    </template>
  </PageHeader>

  <StateBlock v-if="matrix === null && status !== 'error'" state="loading" title="Считаем категории…" />
  <StateBlock v-else-if="matrix === null" state="error" :text="errorMessage" @retry="load" />

  <template v-else>
    <div class="stats">
      <StatTile
        :label="hasFilters ? 'Кандидатов в выборке' : 'Всего кандидатов'"
        :value="matrix.total_candidates"
        :hint="hasFilters ? 'с учётом выбранных срезов' : 'открыли профиль работодателям'"
        tone="primary"
      />
      <StatTile
        label="С результатами ФСП"
        :value="matrix.fsp_verified_total"
        :hint="fspShare || 'есть достижения из реестра'"
        tone="success"
      />
      <StatTile
        class="stats__wide"
        label="Категорий с кандидатами"
        :value="matrix.cells.length"
        hint="ячеек в матрице «стек × грейд»"
      />
    </div>

    <div v-if="hasFilters" class="filterbar" role="group" aria-label="Срезы матрицы">
      <span class="filterbar__title">Матрица сужена:</span>
      <button
        v-if="roleFilter"
        type="button"
        class="filterbar__chip"
        :aria-label="`Снять срез: роль ${reference.teamRoleTitle(roleFilter)}`"
        @click="setMatrixFilter('team_role', null)"
      >
        Роль: {{ reference.teamRoleTitle(roleFilter) }}
        <AppIcon name="x" :size="14" />
      </button>
      <button
        v-if="formatFilter"
        type="button"
        class="filterbar__chip"
        :aria-label="`Снять срез: формат ${reference.workFormatTitle(formatFilter)}`"
        @click="setMatrixFilter('work_format', null)"
      >
        Формат: {{ reference.workFormatTitle(formatFilter) }}
        <AppIcon name="x" :size="14" />
      </button>
      <AppButton variant="ghost" size="sm" @click="resetFilters">Сбросить</AppButton>
      <AppButton variant="secondary" size="sm" :to="searchLocation(carry)">Открыть выборку в поиске</AppButton>
    </div>

    <StateBlock
      v-if="matrix.total_candidates === 0"
      state="empty"
      :title="hasFilters ? 'В этом срезе пока никого нет' : 'Открытых профилей пока нет'"
      :text="
        hasFilters
          ? 'Попробуйте другую роль или формат работы: матрица пересчитывается по выбранному срезу.'
          : 'Кандидаты появятся здесь, как только разрешат работодателям видеть свой профиль.'
      "
    >
      <template v-if="hasFilters" #action>
        <AppButton variant="secondary" @click="resetFilters">Сбросить срезы</AppButton>
      </template>
    </StateBlock>

    <div v-else class="board" :class="{ 'is-reloading': status === 'loading' }" :aria-busy="status === 'loading'">
      <section class="board__matrix card" aria-labelledby="matrix-title">
        <header class="board__head">
          <h2 id="matrix-title" class="board__title">Стек × грейд</h2>
          <p class="board__hint">
            {{ formatCount(matrix.total_candidates, CANDIDATES) }} в {{ matrix.cells.length }} категориях. Нажмите на
            ячейку: откроется поиск именно по этой категории.
          </p>
          <p class="board__hint">
            В поиске по Backend и Frontend показываются и Fullstack-кандидаты, поэтому там может быть чуть больше,
            чем в ячейке.
          </p>
        </header>
        <HeatMatrix :matrix="matrix" :carry="carry" />
      </section>

      <div class="board__slices">
        <SliceList
          title="По роли в команде"
          hint="Нажмите на роль, чтобы сузить матрицу. Стрелка ведёт в поиск."
          mode="filter"
          :items="roleSlices"
          :active-key="roleFilter"
          @select="toggleRole"
        />
        <SliceList
          title="По формату работы"
          hint="Так же сужает матрицу."
          mode="filter"
          :items="formatSlices"
          :active-key="formatFilter"
          @select="toggleFormat"
        />
        <SliceList
          title="По дисциплинам ФСП"
          hint="Сколько кандидатов с результатами в дисциплине. Нажмите — откроется поиск."
          mode="link"
          :items="disciplineSlices"
        />
      </div>
    </div>
  </template>
</template>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3);
}
.stats__wide {
  grid-column: 1 / -1;
}
@media (min-width: 640px) {
  .stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--sp-4);
  }
  .stats__wide {
    grid-column: auto;
  }
}

.filterbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--c-primary-soft-2);
  border-radius: var(--r-lg);
  background: var(--c-primary-soft);
}
.filterbar__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-ink);
}
.filterbar__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 4px 8px 4px 12px;
  border: 1px solid var(--c-primary);
  border-radius: var(--r-pill);
  background: var(--c-surface);
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 600;
}
.filterbar__chip:hover {
  background: var(--c-primary);
  color: #fff;
}

.board {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-5);
  align-items: start;
  transition: opacity var(--t-base) var(--ease);
}
.board.is-reloading {
  opacity: 0.55;
  pointer-events: none;
}
.board__matrix {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
  padding: var(--sp-4);
}
.board__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.board__title {
  font-size: var(--fs-lg);
}
.board__hint {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  line-height: 1.45;
}
.board__slices {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
  min-width: 0;
}

@media (min-width: 640px) {
  .board__matrix {
    padding: var(--sp-6);
  }
}
@media (min-width: 640px) and (max-width: 1099px) {
  .board__slices {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: start;
  }
}
@media (min-width: 1100px) {
  .board {
    grid-template-columns: minmax(0, 1.75fr) minmax(280px, 1fr);
  }
}
</style>
