<script setup lang="ts">
import { computed } from 'vue'

import type { Fact } from '@/api/types'
import AppIcon from '@/components/AppIcon.vue'
import { useReferenceStore } from '@/stores/reference'
import { achievementFactValue, achievementYear, isHttpUrl } from '@/utils/facts'
import { formatDate, formatNumber } from '@/utils/format'

import { fspTeamRoleTitle, pickFacts } from './helpers'

// Results imported from the registry, grouped by year (newest first). Every row links to the protocol.
const props = defineProps<{ facts: readonly Fact[] }>()

const reference = useReferenceStore()

type ResultRow = {
  id: number
  title: string
  place: number | null
  prize: boolean
  meta: string
  team: string | null
  protocol: string | null
  sortKey: string
}

type YearGroup = { year: number | null; label: string; rows: ResultRow[] }

function toRow(fact: Fact): ResultRow {
  const value = achievementFactValue(fact)
  const metaParts: string[] = []
  if (value.discipline !== null) {
    metaParts.push(reference.disciplineTitle(value.discipline))
  }
  metaParts.push(reference.levelTitle(value.level))
  if (value.date !== null) {
    metaParts.push(formatDate(value.date))
  }
  if (value.participants_total !== null) {
    metaParts.push(`участников: ${formatNumber(value.participants_total)}`)
  }
  const teamParts: string[] = []
  if (value.team_name !== null) {
    teamParts.push(`команда «${value.team_name}»`)
  }
  const role = fspTeamRoleTitle(value.team_role)
  if (role !== null) {
    teamParts.push(role)
  }
  const link = value.document_url ?? fact.evidence
  return {
    id: fact.id,
    title: value.title,
    place: value.place,
    prize: value.place !== null && value.place <= 3,
    meta: metaParts.join(' · '),
    team: teamParts.length > 0 ? teamParts.join(' · ') : null,
    protocol: isHttpUrl(link) ? link : null,
    sortKey: value.date ?? '',
  }
}

const groups = computed<YearGroup[]>(() => {
  const byYear = new Map<number | null, ResultRow[]>()
  for (const fact of pickFacts(props.facts, 'achievement', 'fsp')) {
    const year = achievementYear(fact)
    const list = byYear.get(year) ?? []
    list.push(toRow(fact))
    byYear.set(year, list)
  }
  return [...byYear.entries()]
    .sort(([a], [b]) => (b ?? 0) - (a ?? 0))
    .map(([year, rows]) => ({
      year,
      label: year === null ? 'Без даты' : String(year),
      rows: [...rows].sort((a, b) => b.sortKey.localeCompare(a.sortKey)),
    }))
})

const total = computed(() => groups.value.reduce((sum, group) => sum + group.rows.length, 0))
const demoNote = computed(() => reference.isMock)
</script>

<template>
  <div v-if="total > 0" class="res">
    <section v-for="group in groups" :key="group.label" class="res__group">
      <h3 class="section-title">
        <span class="num">{{ group.label }}</span>
        <span class="res__count num">{{ group.rows.length }}</span>
      </h3>
      <ul class="res__list">
        <li v-for="row in group.rows" :key="row.id" class="res__row">
          <span
            class="res__place num"
            :class="{ 'is-prize': row.prize }"
            :title="row.place === null ? 'Место не указано' : `${row.place} место`"
          >
            <template v-if="row.place !== null">{{ row.place }}</template>
            <template v-else>—</template>
            <span class="sr-only">место</span>
          </span>
          <div class="res__body">
            <p class="res__title">{{ row.title }}</p>
            <p class="res__meta">{{ row.meta }}</p>
            <p v-if="row.team" class="res__team">{{ row.team }}</p>
          </div>
          <a
            v-if="row.protocol"
            class="res__link"
            :href="row.protocol"
            target="_blank"
            rel="noopener noreferrer"
            :title="demoNote ? 'Демо-стенд: адрес протокола вымышленный, страница не откроется' : undefined"
          >
            Протокол <AppIcon name="external" :size="14" />
          </a>
        </li>
      </ul>
    </section>
    <p v-if="demoNote" class="res__note">
      Демо-стенд: результаты и адреса протоколов вымышлены, в рабочей версии ссылка ведёт на протокол в реестре ФСП.
    </p>
  </div>
</template>

<style scoped>
.res {
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}
.res__group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.res__count {
  font-weight: 500;
  color: var(--c-text-faint);
}
.res__list {
  list-style: none;
  display: flex;
  flex-direction: column;
}
.res__row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: var(--sp-2) var(--sp-4);
  align-items: start;
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.res__row:last-child {
  border-bottom: 0;
}
.res__place {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: var(--r-md);
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
  font-size: var(--fs-lg);
  font-weight: 700;
}
.res__place.is-prize {
  background: var(--c-primary);
  color: #fff;
}
.res__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.res__title {
  font-weight: 600;
  line-height: 1.4;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.res__meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.res__team {
  font-size: var(--fs-sm);
  color: var(--c-ink);
}
.res__link {
  grid-column: 2;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  justify-self: start;
  font-size: var(--fs-sm);
  font-weight: 500;
}
.res__note {
  font-size: var(--fs-xs);
  line-height: 1.5;
  color: var(--c-text-muted);
}

@media (min-width: 720px) {
  .res__row {
    grid-template-columns: 44px minmax(0, 1fr) auto;
  }
  .res__link {
    grid-column: auto;
    justify-self: end;
    padding-top: 2px;
  }
}
</style>
