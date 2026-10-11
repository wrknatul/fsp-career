<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'

import { getProfile, listTests, startTest } from '@/api/candidate'
import { getErrorMessage, hasErrorCode, serverNow } from '@/api/client'
import type { CandidateProfile, Category, TestInfo, TestResult, TestSession } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useToastStore } from '@/stores/toast'
import { formatCount, formatDate, formatPercent, formatTimeLeft, parseServerDate } from '@/utils/format'

import { sessionGet, sessionRemove, sessionSet } from './components/helpers'
import TestResultPanel from './components/TestResultPanel.vue'
import TestRunner from './components/TestRunner.vue'

// Test list and the whole attempt on one page: start -> questions with a timer -> result.
const toast = useToastStore()

type View = 'list' | 'run' | 'result'
type LoadStatus = 'loading' | 'ready' | 'error'

// Marks "this tab is in the middle of an attempt": after a reload the same session is opened again.
const ACTIVE_KEY = 'fsp_career_test_active'

const status = ref<LoadStatus>('loading')
const errorMessage = ref('')
const tests = shallowRef<TestInfo[]>([])
const profile = shallowRef<CandidateProfile | null>(null)
const view = ref<View>('list')
const session = shallowRef<TestSession | null>(null)
const result = shallowRef<TestResult | null>(null)
const categoryBefore = shallowRef<Category | null>(null)
const startingSkill = ref<string | null>(null)
const pendingStart = shallowRef<TestInfo | null>(null)
const askStart = ref(false)
const nowMs = ref(serverNow())

let disposed = false
let clockId: number | null = null

const passedCount = computed(() => tests.value.filter((test) => test.best_result !== null).length)
const sessionTitle = computed(() => session.value?.title ?? result.value?.skill ?? '')
const resultSkillTitle = computed(() => {
  const skill = result.value?.skill
  return tests.value.find((test) => test.skill === skill)?.title ?? sessionTitle.value
})

function isCooling(test: TestInfo): boolean {
  if (test.available_at === null) {
    return false
  }
  const date = parseServerDate(test.available_at)
  return date !== null && date.getTime() > nowMs.value
}

/** '2026-10-10T14:33:00Z' -> '17:33' in the browser's time zone. */
function clockTime(iso: string | null): string {
  const date = parseServerDate(iso)
  return date === null ? '' : date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function limitText(test: TestInfo): string {
  const minutes = Math.max(1, Math.round(test.time_limit_seconds / 60))
  return `${formatCount(test.questions_per_session, ['вопрос', 'вопроса', 'вопросов'])} · ${formatCount(minutes, ['минута', 'минуты', 'минут'])}`
}

// ---------- Loading ----------

async function refreshQuietly(): Promise<void> {
  try {
    const [list, current] = await Promise.all([listTests(), getProfile()])
    if (disposed) {
      return
    }
    tests.value = list
    profile.value = current
  } catch {
    // The list on screen stays; the next action reports a real error.
  }
}

async function begin(skill: string, resumed: boolean): Promise<void> {
  if (startingSkill.value !== null) {
    return
  }
  startingSkill.value = skill
  try {
    categoryBefore.value = profile.value?.category ?? null
    const started = await startTest(skill)
    if (disposed) {
      return
    }
    session.value = started
    result.value = null
    view.value = 'run'
    sessionSet(ACTIVE_KEY, String(started.session_id))
    window.scrollTo({ top: 0 })
    if (resumed) {
      toast.info('Продолжаем начатую попытку: время идёт по часам сервера')
    }
  } catch (err) {
    toast.fromError(err)
    if (hasErrorCode(err, 'TEST_COOLDOWN')) {
      void refreshQuietly()
    }
  } finally {
    startingSkill.value = null
  }
}

async function resumeIfMarked(): Promise<void> {
  const marker = sessionGet(ACTIVE_KEY)
  if (marker === null) {
    return
  }
  const open = tests.value.find((test) => test.active_session_id !== null && String(test.active_session_id) === marker)
  if (open === undefined) {
    sessionRemove(ACTIVE_KEY)
    return
  }
  await begin(open.skill, true)
}

async function load(): Promise<void> {
  status.value = 'loading'
  errorMessage.value = ''
  try {
    const [list, current] = await Promise.all([listTests(), getProfile()])
    if (disposed) {
      return
    }
    tests.value = list
    profile.value = current
    status.value = 'ready'
  } catch (err) {
    if (!disposed) {
      errorMessage.value = getErrorMessage(err)
      status.value = 'error'
    }
    return
  }
  await resumeIfMarked()
}

onMounted(() => {
  void load()
  clockId = window.setInterval(() => {
    nowMs.value = serverNow()
  }, 15_000)
})

onBeforeUnmount(() => {
  disposed = true
  if (clockId !== null) {
    window.clearInterval(clockId)
  }
})

// ---------- Actions ----------

function onStartClick(test: TestInfo): void {
  if (test.active_session_id !== null) {
    void begin(test.skill, false)
    return
  }
  pendingStart.value = test
  askStart.value = true
}

async function confirmStart(): Promise<void> {
  const test = pendingStart.value
  if (test === null) {
    return
  }
  await begin(test.skill, false)
  askStart.value = false
}

function onFinished(finished: TestResult): void {
  sessionRemove(ACTIVE_KEY)
  result.value = finished
  profile.value = finished.profile
  view.value = 'result'
  window.scrollTo({ top: 0 })
  void refreshQuietly()
}

function backToList(): void {
  sessionRemove(ACTIVE_KEY)
  view.value = 'list'
  result.value = null
  session.value = null
  window.scrollTo({ top: 0 })
  void refreshQuietly()
}
</script>

<template>
  <template v-if="view === 'run' && session">
    <TestRunner :key="session.session_id" :session="session" @finished="onFinished" @closed="backToList" @leave="backToList" />
  </template>

  <template v-else-if="view === 'result' && result">
    <TestResultPanel :result="result" :before="categoryBefore" :skill-title="resultSkillTitle" @back="backToList" />
  </template>

  <template v-else>
    <PageHeader
      title="Экспресс-тесты"
      eyebrow="Соискатель"
      subtitle="Экспресс-проверка из 6 вопросов: ориентир, а не аттестация. Сданный тест делает навык «Подтверждено тестом» и усиливает опыт из резюме."
    />

    <StateBlock v-if="status === 'loading'" state="loading" title="Загружаем тесты…" />
    <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />
    <StateBlock
      v-else-if="tests.length === 0"
      state="empty"
      title="Тестов пока нет"
      text="Когда они появятся, здесь можно будет подтвердить навыки за несколько минут."
    />

    <template v-else>
      <p class="rules">
        <AppIcon name="info" :size="16" />
        <span>
          Таймер запускается сразу и идёт по часам сервера, перезагрузка страницы его не останавливает. Уровень ниже
          «Базового» в профиль не попадает. Пересдавать можно после паузы.
          <template v-if="passedCount > 0"> Сдано тестов: <b class="num">{{ passedCount }}</b> из <b class="num">{{ tests.length }}</b>.</template>
        </span>
      </p>

      <ul class="tests">
        <li v-for="test in tests" :key="test.skill" class="test card">
          <header class="test__head">
            <h2 class="test__title">{{ test.title }}</h2>
            <p class="test__limit num">{{ limitText(test) }}</p>
          </header>
          <p class="test__desc">{{ test.description }}</p>

          <div class="test__best">
            <template v-if="test.best_result">
              <SourceBadge verification="tested" size="sm" />
              <div class="test__best-body">
                <p class="test__best-text">Лучший результат: <b>{{ test.best_result.level_title }}</b></p>
                <p class="test__best-meta num">
                  {{ formatPercent(test.best_result.score) }} от максимума · {{ formatDate(test.best_result.submitted_at) }}
                </p>
              </div>
            </template>
            <p v-else class="test__best-text muted">Ещё не сдавали</p>
          </div>

          <p v-if="test.active_session_id !== null" class="test__state test__state--open">
            <AppIcon name="alert" :size="14" />Есть незавершённая попытка, её можно продолжить.
          </p>
          <p v-else-if="isCooling(test)" class="test__state">
            <AppIcon name="lock" :size="14" />
            <span>
              Пересдать можно через <b class="num">{{ formatTimeLeft(test.available_at, nowMs) }}</b> <span class="muted">(в {{ clockTime(test.available_at) }})</span>
            </span>
          </p>

          <div class="test__action">
            <AppButton
              v-if="test.active_session_id !== null"
              :loading="startingSkill === test.skill"
              :disabled="startingSkill !== null"
              @click="onStartClick(test)"
            >
              Продолжить
            </AppButton>
            <AppButton
              v-else-if="isCooling(test)"
              variant="secondary"
              disabled
            >
              Пока нельзя
            </AppButton>
            <AppButton
              v-else
              :variant="test.best_result ? 'secondary' : 'primary'"
              :loading="startingSkill === test.skill"
              :disabled="startingSkill !== null"
              @click="onStartClick(test)"
            >
              {{ test.best_result ? 'Пересдать' : 'Пройти тест' }}
            </AppButton>
          </div>
        </li>
      </ul>
    </template>

    <ConfirmModal
      v-model="askStart"
      :title="pendingStart ? `Начать тест «${pendingStart.title}»?` : 'Начать тест?'"
      :message="
        pendingStart
          ? `${limitText(pendingStart)}. Таймер запустится сразу, неотвеченные вопросы засчитаются как неверные. После попытки будет пауза перед пересдачей.`
          : ''
      "
      confirm-label="Начать"
      :loading="startingSkill !== null"
      @confirm="confirmStart"
    />
  </template>
</template>

<style scoped>
.rules {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-primary-soft);
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-ink);
}
.rules :deep(svg) {
  margin-top: 3px;
  color: var(--c-primary);
}
.tests {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr));
  gap: var(--sp-4);
}
.test {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.test__head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.test__title {
  font-size: var(--fs-xl);
}
.test__limit {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.test__desc {
  flex: 1;
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-text-muted);
}
.test__best {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--c-border);
}
.test__best-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.test__best-text {
  font-size: var(--fs-sm);
}
.test__best-meta {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.test__state {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.test__state--open {
  color: var(--c-warning-text);
  font-weight: 500;
}
.test__action {
  display: flex;
}
</style>
