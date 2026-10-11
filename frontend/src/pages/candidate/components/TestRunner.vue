<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { submitTest } from '@/api/candidate'
import { hasErrorCode, serverNow } from '@/api/client'
import type { TestResult, TestSession } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { useToastStore } from '@/stores/toast'
import { formatCountdown, parseServerDate } from '@/utils/format'

import { sessionGet, sessionRemove, sessionSet } from './helpers'
import QuestionText from './QuestionText.vue'

// Taking a test: server-clock timer, one question at a time, answers kept in sessionStorage across reloads.
// The page above owns the session: it starts it and reacts to `finished` / `closed` / `leave`.
const props = defineProps<{ session: TestSession }>()
const emit = defineEmits<{
  finished: [result: TestResult]
  /** The server no longer accepts this session (time is up on the server, already submitted). */
  closed: []
  /** The candidate went back to the list; the attempt stays open on the server until time runs out. */
  leave: []
}>()

const toast = useToastStore()

// Submit a little before the deadline: the request needs time to reach the server, which rejects late answers.
const AUTO_SUBMIT_LEAD_MS = 3000
const LOW_TIME_SECONDS = 60
const FALLBACK_LIMIT_MS = 8 * 60 * 1000

const storageKey = computed(() => `fsp_career_test_${props.session.session_id}`)
const questions = computed(() => props.session.questions)
const total = computed(() => questions.value.length)

type Saved = { answers: Record<string, number>; index: number }

function restore(): Saved {
  const empty: Saved = { answers: {}, index: 0 }
  const raw = sessionGet(storageKey.value)
  if (raw === null) {
    return empty
  }
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) {
      return empty
    }
    const record = parsed as Record<string, unknown>
    const answers: Record<string, number> = {}
    const rawAnswers = record.answers
    if (typeof rawAnswers === 'object' && rawAnswers !== null) {
      for (const question of questions.value) {
        const value = (rawAnswers as Record<string, unknown>)[question.id]
        if (typeof value === 'number' && Number.isInteger(value) && value >= 0 && value < question.options.length) {
          answers[question.id] = value
        }
      }
    }
    const index = typeof record.index === 'number' && record.index >= 0 && record.index < total.value ? record.index : 0
    return { answers, index }
  } catch {
    return empty
  }
}

const saved = restore()
const answers = ref<Record<string, number>>(saved.answers)
const index = ref(saved.index)
const submitting = ref(false)
const confirmOpen = ref(false)
const submitFailed = ref(false)

const question = computed(() => questions.value[index.value])
const answeredCount = computed(() => questions.value.filter((item) => answers.value[item.id] !== undefined).length)
const missingCount = computed(() => total.value - answeredCount.value)

function persist(): void {
  sessionSet(storageKey.value, JSON.stringify({ answers: answers.value, index: index.value }))
}

function select(questionId: string, optionIndex: number): void {
  answers.value = { ...answers.value, [questionId]: optionIndex }
  persist()
}

function go(next: number): void {
  index.value = Math.min(total.value - 1, Math.max(0, next))
  persist()
}

// ---------- Timer (server clock) ----------

const expiresMs = (() => {
  const parsed = parseServerDate(props.session.expires_at)
  return parsed === null ? serverNow() + FALLBACK_LIMIT_MS : parsed.getTime()
})()

const now = ref(serverNow())
const remainingSeconds = computed(() => Math.max(0, Math.ceil((expiresMs - now.value) / 1000)))
const isLow = computed(() => remainingSeconds.value <= LOW_TIME_SECONDS)
let tickId: number | null = null
let autoStarted = false

function tick(): void {
  now.value = serverNow()
}

watch(now, (value) => {
  if (!autoStarted && expiresMs - value <= AUTO_SUBMIT_LEAD_MS) {
    autoStarted = true
    void submit(true)
  }
})

// The timer bar sticks right under the sticky cabinet header, whatever its height is at this width.
const stickyTop = ref(0)

function measureHeader(): void {
  const header = document.querySelector<HTMLElement>('.topbar')
  stickyTop.value = header === null ? 0 : header.offsetHeight + 8
}

// The button that opened the test is gone from the DOM: move focus to the test title so keyboard and
// screen-reader users start inside the test instead of at the top of the page.
const titleRef = ref<HTMLElement | null>(null)

onMounted(() => {
  titleRef.value?.focus({ preventScroll: true })
  tick()
  measureHeader()
  tickId = window.setInterval(tick, 250)
  document.addEventListener('visibilitychange', tick)
  window.addEventListener('resize', measureHeader)
})

onBeforeUnmount(() => {
  if (tickId !== null) {
    window.clearInterval(tickId)
  }
  document.removeEventListener('visibilitychange', tick)
  window.removeEventListener('resize', measureHeader)
})

// ---------- Submit ----------

function requestSubmit(): void {
  if (missingCount.value > 0) {
    confirmOpen.value = true
    return
  }
  void submit(false)
}

async function submit(auto: boolean): Promise<void> {
  if (submitting.value) {
    return
  }
  submitting.value = true
  submitFailed.value = false
  confirmOpen.value = false
  try {
    const result = await submitTest(props.session.session_id, { answers: { ...answers.value } })
    sessionRemove(storageKey.value)
    emit('finished', result)
  } catch (err) {
    toast.fromError(err)
    if (hasErrorCode(err, 'TEST_SESSION_EXPIRED') || hasErrorCode(err, 'TEST_ALREADY_SUBMITTED') || hasErrorCode(err, 'TEST_NOT_FOUND')) {
      sessionRemove(storageKey.value)
      emit('closed')
      return
    }
    submitFailed.value = true
    if (auto) {
      // Let the candidate retry by hand while the server still accepts the answers.
      toast.info('Ответы не ушли автоматически. Нажмите «Отправить ещё раз», пока сервер их принимает.')
    }
  } finally {
    submitting.value = false
  }
}

function leave(): void {
  persist()
  emit('leave')
}

function difficultyLabel(level: number): string {
  return `Сложность ${level} из 3`
}
</script>

<template>
  <section class="run" aria-labelledby="run-title">
    <header class="run__bar" :style="{ top: `${stickyTop}px` }">
      <div class="run__who">
        <p class="eyebrow">Экспресс-тест</p>
        <h2 id="run-title" ref="titleRef" class="run__title" tabindex="-1">{{ session.title }}</h2>
      </div>
      <div class="run__timer" :class="{ 'is-low': isLow }" role="timer" aria-label="Осталось времени">
        <AppIcon name="alert" :size="16" v-if="isLow" />
        <span class="run__time num">{{ formatCountdown(remainingSeconds) }}</span>
        <span class="run__time-cap">{{ remainingSeconds === 0 ? 'время вышло' : isLow ? 'осталась минута' : 'осталось' }}</span>
      </div>
    </header>

    <div class="run__progress">
      <p class="run__count">
        Отвечено <b class="num">{{ answeredCount }}</b> из <b class="num">{{ total }}</b>
      </p>
      <ol class="run__dots" aria-label="Вопросы">
        <li v-for="(item, position) in questions" :key="item.id">
          <button
            type="button"
            class="dot num"
            :class="{ 'is-current': position === index, 'is-answered': answers[item.id] !== undefined }"
            :aria-label="`Вопрос ${position + 1}${answers[item.id] !== undefined ? ', ответ выбран' : ', без ответа'}`"
            :aria-current="position === index ? 'step' : undefined"
            @click="go(position)"
          >
            {{ position + 1 }}
          </button>
        </li>
      </ol>
    </div>

    <article v-if="question" class="card run__card">
      <p class="run__meta">
        <span class="num">Вопрос {{ index + 1 }} из {{ total }}</span>
        <span class="run__diff">{{ difficultyLabel(question.difficulty) }}</span>
      </p>
      <QuestionText :text="question.text" class="run__text" />

      <fieldset class="opts">
        <legend class="sr-only">Варианты ответа</legend>
        <label
          v-for="(option, optionIndex) in question.options"
          :key="`${question.id}-${optionIndex}`"
          class="opt"
          :class="{ 'is-on': answers[question.id] === optionIndex }"
        >
          <input
            class="opt__input"
            type="radio"
            :name="`question-${question.id}`"
            :value="optionIndex"
            :checked="answers[question.id] === optionIndex"
            @change="select(question.id, optionIndex)"
          />
          <span class="opt__mark num" aria-hidden="true">{{ optionIndex + 1 }}</span>
          <QuestionText :text="option" inline class="opt__text" />
        </label>
      </fieldset>
    </article>

    <div class="run__nav">
      <div class="run__nav-steps">
        <AppButton variant="ghost" :disabled="index === 0 || submitting" @click="go(index - 1)">Назад</AppButton>
        <AppButton
          v-if="index < total - 1"
          variant="secondary"
          :disabled="submitting"
          @click="go(index + 1)"
        >
          Дальше
        </AppButton>
      </div>
      <AppButton :loading="submitting" @click="requestSubmit">
        {{ submitFailed ? 'Отправить ещё раз' : 'Сдать тест' }}
      </AppButton>
    </div>

    <p class="run__foot">
      Ответы можно менять до сдачи. Время идёт по часам сервера, перезагрузка страницы тест не прерывает.
      <button type="button" class="run__leave link" :disabled="submitting" @click="leave">К списку тестов</button>
    </p>

    <ConfirmModal
      v-model="confirmOpen"
      title="Сдать с пропусками?"
      :message="`Вы ответили на ${answeredCount} из ${total}. Вопросы без ответа засчитаются как неверные, исправить уже не получится.`"
      confirm-label="Сдать тест"
      cancel-label="Вернуться к вопросам"
      :loading="submitting"
      @confirm="submit(false)"
    />
  </section>
</template>

<style scoped>
.run {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  max-width: 760px;
  width: 100%;
  margin-inline: auto;
}
.run__bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3) var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}
.run__who {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.run__title {
  font-size: var(--fs-lg);
  overflow-wrap: anywhere;
}
.run__timer {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 14px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-ink);
}
.run__timer.is-low {
  background: var(--c-danger-soft);
  color: var(--c-danger-text);
}
.run__timer :deep(svg) {
  align-self: center;
}
.run__time {
  font-size: var(--fs-xl);
  font-weight: 700;
  line-height: 1;
}
.run__time-cap {
  font-size: var(--fs-xs);
  font-weight: 600;
}
.run__progress {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.run__count {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.run__count b {
  color: var(--c-ink);
}
.run__dots {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.dot {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1.5px solid var(--c-border-strong);
  border-radius: 50%;
  background: var(--c-surface);
  color: var(--c-text-muted);
  font-size: var(--fs-sm);
  font-weight: 600;
  transition:
    background var(--t-fast) var(--ease),
    border-color var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease);
}
.dot.is-answered {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.dot.is-current {
  border-color: var(--c-primary);
  background: var(--c-primary);
  color: #fff;
}
.run__card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.run__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.run__diff {
  padding: 1px 10px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-neutral-text);
}
.run__text {
  font-size: var(--fs-md);
  font-weight: 500;
  line-height: 1.55;
  color: var(--c-ink);
}
.opts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.opt {
  position: relative;
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  padding: var(--sp-3) var(--sp-4);
  border: 1.5px solid var(--c-border-strong);
  border-radius: var(--r-md);
  background: var(--c-surface);
  cursor: pointer;
  transition:
    border-color var(--t-fast) var(--ease),
    background var(--t-fast) var(--ease);
}
.opt:hover {
  border-color: var(--c-primary);
}
.opt.is-on {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
.opt:has(.opt__input:focus-visible) {
  box-shadow: var(--ring);
  border-color: var(--c-primary);
}
.opt__input {
  position: absolute;
  opacity: 0;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  cursor: pointer;
}
.opt__mark {
  flex: none;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
  font-size: var(--fs-xs);
  font-weight: 700;
}
.opt.is-on .opt__mark {
  background: var(--c-primary);
  color: #fff;
}
.opt__text {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
  line-height: 1.5;
}
.run__nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.run__nav-steps {
  display: flex;
  gap: var(--sp-2);
}
.run__foot {
  font-size: var(--fs-xs);
  line-height: 1.6;
  color: var(--c-text-muted);
}
.run__leave {
  padding: 0;
  border: 0;
  background: none;
  font-size: inherit;
}
</style>
