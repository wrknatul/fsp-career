<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import type { CandidateProfile, Verification } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { isManualAchievement } from '@/utils/facts'
import { formatCount, formatDate } from '@/utils/format'

import { pickFacts } from './helpers'

// Four sources of the profile with a status and a jump to the place where it is filled in.
const props = defineProps<{ profile: CandidateProfile }>()

type Row = {
  id: 'fsp' | 'resume' | 'tests' | 'manual'
  title: string
  done: boolean
  status: string
  /** Identifier set in the mono font before the detail text (FSP ID). */
  idText?: string
  detail: string
  verification: Verification
  to: RouteLocationRaw
  action: string
}

const rows = computed<Row[]>(() => {
  const profile = props.profile
  const fspResults = pickFacts(profile.facts, 'achievement', 'fsp').length
  const testsPassed = pickFacts(profile.facts, 'skill', 'test').length
  const manual = profile.facts.filter(isManualAchievement).length

  const fspRow: Row =
    profile.fsp !== null
      ? {
          id: 'fsp',
          title: 'Реестр ФСП',
          done: true,
          status: 'Привязан',
          idText: profile.fsp.fsp_id,
          detail: formatCount(fspResults, ['результат', 'результата', 'результатов']),
          verification: 'verified',
          to: '/candidate/fsp',
          action: 'Открыть',
        }
      : {
          id: 'fsp',
          title: 'Реестр ФСП',
          done: false,
          status: 'Не привязан',
          detail: 'Результаты соревнований и разряд — самое сильное подтверждение: до 50 из 100 в индексе.',
          verification: 'verified',
          to: '/candidate/fsp',
          action: 'Привязать',
        }

  const resumeRow: Row =
    profile.resume !== null
      ? {
          id: 'resume',
          title: 'Резюме',
          done: true,
          status: 'Разобрано',
          detail: `${profile.resume.filename ?? 'Вставленный текст'} · ${formatDate(profile.resume.parsed_at)}`,
          verification: 'parsed',
          to: { path: '/candidate/profile', hash: '#resume' },
          action: 'Открыть',
        }
      : {
          id: 'resume',
          title: 'Резюме',
          done: false,
          status: 'Не загружено',
          detail: 'Из резюме берутся навыки и опыт работы, а опыт определяет грейд. В индекс оно не входит.',
          verification: 'parsed',
          to: { path: '/candidate/profile', hash: '#resume' },
          action: 'Добавить',
        }

  const testsRow: Row =
    testsPassed > 0
      ? {
          id: 'tests',
          title: 'Экспресс-тесты',
          done: true,
          status: `Сдано: ${formatCount(testsPassed, ['тест', 'теста', 'тестов'])}`,
          detail: 'Каждый сданный тест подтверждает навык. В индекс идут два лучших.',
          verification: 'tested',
          to: '/candidate/tests',
          action: 'К тестам',
        }
      : {
          id: 'tests',
          title: 'Экспресс-тесты',
          done: false,
          status: 'Не сдано',
          detail: 'Шесть вопросов, восемь минут. Каждый тест даёт +25 к индексу, считаются два.',
          verification: 'tested',
          to: '/candidate/tests',
          action: 'Пройти',
        }

  const manualRow: Row =
    manual > 0
      ? {
          id: 'manual',
          title: 'Достижения вручную',
          done: true,
          status: `Добавлено: ${manual}`,
          detail: 'Не подтверждено. Вклад в грейд — 35%.',
          verification: 'declared',
          to: { path: '/candidate/profile', hash: '#achievements' },
          action: 'Открыть',
        }
      : {
          id: 'manual',
          title: 'Достижения вручную',
          done: false,
          status: 'Нет',
          detail: 'Олимпиады, хакатоны, CTF вне реестра. Не подтверждено: вклад в грейд — 35%.',
          verification: 'declared',
          to: { path: '/candidate/profile', hash: '#achievements' },
          action: 'Добавить',
        }

  return [fspRow, resumeRow, testsRow, manualRow]
})
</script>

<template>
  <ul class="src card">
    <li v-for="row in rows" :key="row.id" class="src__row" :class="{ 'is-done': row.done }">
      <span class="src__mark" aria-hidden="true"><AppIcon v-if="row.done" name="check" :size="14" /></span>
      <div class="src__body">
        <div class="src__head">
          <h3 class="src__title">{{ row.title }}</h3>
          <span class="src__status" :class="row.done ? 'is-done' : 'is-todo'">{{ row.status }}</span>
        </div>
        <p class="src__detail">
          <span v-if="row.idText" class="src__id mono">{{ row.idText }}</span
          >{{ row.detail }}
        </p>
      </div>
      <div class="src__side">
        <SourceBadge :verification="row.verification" size="sm" />
        <AppButton :to="row.to" :variant="row.done ? 'secondary' : 'primary'" size="sm">{{ row.action }}</AppButton>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.src {
  list-style: none;
  display: flex;
  flex-direction: column;
  padding: 0;
}
.src__row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: var(--sp-3) var(--sp-4);
  align-items: start;
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--c-border);
}
.src__row:last-child {
  border-bottom: 0;
}
.src__mark {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin-top: 2px;
  border-radius: 50%;
  border: 1.5px dashed var(--c-border-strong);
  color: #fff;
}
.src__row.is-done .src__mark {
  border: 0;
  background: var(--c-success);
}
.src__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.src__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px var(--sp-3);
}
.src__title {
  font-size: var(--fs-base);
}
.src__status {
  font-size: var(--fs-sm);
  font-weight: 600;
}
.src__status.is-done {
  color: var(--c-success-text);
}
.src__status.is-todo {
  color: var(--c-warning-text);
}
.src__detail {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
  overflow-wrap: anywhere;
}
.src__id {
  color: var(--c-ink);
}
/* The separator lives in CSS: Vue drops whitespace between an element and the next text on a new line. */
.src__id::after {
  content: '·';
  margin: 0 var(--sp-2);
  color: var(--c-text-muted);
}
.src__side {
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
}

@media (min-width: 720px) {
  .src__row {
    grid-template-columns: 24px minmax(0, 1fr) auto;
    align-items: center;
  }
  .src__side {
    grid-column: auto;
    justify-content: flex-end;
    gap: var(--sp-4);
  }
}
</style>
