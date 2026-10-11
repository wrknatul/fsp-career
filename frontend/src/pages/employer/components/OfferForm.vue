<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { fieldErrors, hasErrorCode } from '@/api/client'
import { createOffer } from '@/api/employer'
import type { CandidateCard, Vacancy } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppInput from '@/components/AppInput.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTextarea from '@/components/AppTextarea.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useToastStore } from '@/stores/toast'
import { formatMoney, formatMoneyRange } from '@/utils/format'

// "Send an offer" form on the candidate card: own active vacancy, salary (required), message.
// The salary field gets a hint with the vacancy range and what the candidate expects; the offer cannot be
// taken back in this version, so the send goes through a confirmation.
//   <OfferForm :card="card" :vacancies="vacancies" :status="vacanciesStatus" :preset-vacancy-id="3" @sent="reload" />
const props = defineProps<{
  card: CandidateCard
  vacancies: readonly Vacancy[]
  /** State of loading the own vacancies. */
  status: 'idle' | 'loading' | 'ready' | 'error'
  errorMessage?: string
  presetVacancyId?: number | null
}>()

const emit = defineEmits<{
  /** The offer was created: reload the card. */
  sent: []
  /** The data on the page is stale (the vacancy was archived, the offer already exists): reload it. */
  stale: []
  /** "Повторить" after a failed load of the vacancies. */
  retry: []
}>()

const MAX_MESSAGE = 1000
const MAX_SALARY = 100_000_000

const toast = useToastStore()

const vacancyId = ref<number | null>(null)
const salary = ref<number | null>(null)
const message = ref('')
const errors = ref<Record<string, string>>({})
const confirmOpen = ref(false)
const busy = ref(false)

const activeVacancies = computed(() => props.vacancies.filter((vacancy) => vacancy.is_active))
const sentVacancyIds = computed(() => new Set(props.card.offers.map((offer) => offer.vacancy_id)))
const freeVacancies = computed(() => activeVacancies.value.filter((vacancy) => !sentVacancyIds.value.has(vacancy.id)))

const vacancyOptions = computed(() =>
  activeVacancies.value.map((vacancy) => {
    const sent = sentVacancyIds.value.has(vacancy.id)
    return { value: vacancy.id, label: sent ? `${vacancy.title} — оффер уже отправлен` : vacancy.title, disabled: sent }
  }),
)

const selectedVacancy = computed(() => freeVacancies.value.find((vacancy) => vacancy.id === vacancyId.value) ?? null)

// Preselect: the vacancy the search was run for, or the only one left.
watch(
  freeVacancies,
  (list) => {
    if (vacancyId.value !== null && list.some((vacancy) => vacancy.id === vacancyId.value)) {
      return
    }
    const preset = list.find((vacancy) => vacancy.id === props.presetVacancyId)
    if (preset !== undefined) {
      vacancyId.value = preset.id
    } else if (list.length === 1) {
      vacancyId.value = list[0].id
    } else {
      vacancyId.value = null
    }
  },
  { immediate: true },
)

const expectation = computed(() => props.card.salary_expectation)

const salaryHint = computed(() => {
  const parts: string[] = []
  if (selectedVacancy.value !== null) {
    const range = formatMoneyRange(selectedVacancy.value.salary_from, selectedVacancy.value.salary_to, '')
    if (range !== '') {
      parts.push(`Вилка вакансии: ${range}`)
    }
  }
  parts.push(expectation.value === null ? 'Кандидат не назвал ожидания' : `Ожидания кандидата: ${formatMoney(expectation.value)}`)
  return `${parts.join('. ')}.`
})

type Quick = { key: string; label: string; value: number }

const quickValues = computed<Quick[]>(() => {
  const list: Quick[] = []
  const vacancy = selectedVacancy.value
  if (expectation.value !== null) {
    list.push({ key: 'expect', label: 'Как ждёт кандидат', value: expectation.value })
  }
  if (vacancy !== null && vacancy.salary_from !== null && vacancy.salary_to !== null && vacancy.salary_from !== vacancy.salary_to) {
    list.push({ key: 'mid', label: 'Середина вилки', value: Math.round((vacancy.salary_from + vacancy.salary_to) / 2 / 1000) * 1000 })
  }
  if (vacancy !== null && vacancy.salary_to !== null) {
    list.push({ key: 'top', label: 'Верх вилки', value: vacancy.salary_to })
  }
  return list
})

/** A soft remark about the number, not an error: an HR may know better. */
const salaryNote = computed<{ tone: 'warning' | 'info'; text: string } | null>(() => {
  const value = salary.value
  if (value === null || value <= 0) {
    return null
  }
  if (expectation.value !== null && value < expectation.value) {
    return {
      tone: 'warning',
      text: `Это на ${formatMoney(expectation.value - value)} ниже ожиданий кандидата: вероятность отказа выше.`,
    }
  }
  const vacancy = selectedVacancy.value
  if (vacancy !== null && vacancy.salary_to !== null && value > vacancy.salary_to) {
    return { tone: 'info', text: 'Сумма выше вилки вакансии. Убедитесь, что так и задумано.' }
  }
  if (vacancy !== null && vacancy.salary_from !== null && value < vacancy.salary_from) {
    return { tone: 'info', text: 'Сумма ниже вилки вакансии.' }
  }
  return null
})

function clearError(key: string): void {
  if (errors.value[key] !== undefined) {
    const next = { ...errors.value }
    delete next[key]
    errors.value = next
  }
}

watch(vacancyId, () => clearError('vacancy_id'))
watch(salary, () => clearError('salary'))

function validate(): boolean {
  const next: Record<string, string> = {}
  if (vacancyId.value === null) {
    next.vacancy_id = 'Выберите вакансию, по которой отправляете оффер'
  }
  if (salary.value === null) {
    next.salary = 'Укажите зарплату: оффер без суммы отправить нельзя'
  } else if (!Number.isInteger(salary.value) || salary.value <= 0) {
    next.salary = 'Зарплата — целое число рублей больше нуля'
  } else if (salary.value > MAX_SALARY) {
    next.salary = 'Слишком большая сумма'
  }
  errors.value = next
  return Object.keys(next).length === 0
}

const formRef = ref<HTMLFormElement | null>(null)

function askConfirmation(): void {
  if (validate()) {
    confirmOpen.value = true
    return
  }
  // Put the cursor into the first field with a mistake.
  void nextTick().then(() => {
    formRef.value?.querySelector<HTMLElement>('.field--error .field__control')?.focus()
  })
}

async function send(): Promise<void> {
  if (vacancyId.value === null || salary.value === null) {
    return
  }
  busy.value = true
  try {
    const text = message.value.trim()
    await createOffer({
      candidate_id: props.card.id,
      vacancy_id: vacancyId.value,
      salary: salary.value,
      message: text === '' ? undefined : text,
    })
    confirmOpen.value = false
    toast.success('Оффер отправлен. Кандидат увидит его во входящих.')
    salary.value = null
    message.value = ''
    vacancyId.value = null
    errors.value = {}
    emit('sent')
  } catch (err) {
    confirmOpen.value = false
    errors.value = fieldErrors(err)
    toast.fromError(err)
    if (hasErrorCode(err, 'OFFER_ALREADY_SENT') || hasErrorCode(err, 'VACANCY_INACTIVE') || hasErrorCode(err, 'NOT_FOUND')) {
      emit('stale')
    }
  } finally {
    busy.value = false
  }
}

const confirmText = computed(() => {
  const title = selectedVacancy.value?.title ?? ''
  const sum = salary.value === null ? '' : formatMoney(salary.value)
  return `${props.card.display_name}: ${sum} по вакансии «${title}». В этой версии оффер нельзя отозвать: кандидат ответит на него сам.`
})
</script>

<template>
  <section id="offer" class="offer card" aria-labelledby="offer-title">
    <header class="offer__head">
      <h2 id="offer-title" class="offer__title">Отправить оффер</h2>
      <p class="offer__lead">Кандидат увидит компанию, вакансию и зарплату и ответит сам. Контакты откроются после согласия.</p>
    </header>

    <StateBlock v-if="status === 'loading' || status === 'idle'" state="loading" compact title="Загружаем ваши вакансии…" />
    <StateBlock v-else-if="status === 'error'" state="error" compact :text="errorMessage" @retry="emit('retry')" />

    <StateBlock
      v-else-if="activeVacancies.length === 0"
      state="empty"
      compact
      title="Нужна активная вакансия"
      text="Оффер всегда привязан к вакансии: так кандидат понимает, куда его зовут. Заведите вакансию и вернитесь сюда."
    >
      <template #action>
        <AppButton size="sm" :to="{ name: 'employer-vacancies' }">Создать вакансию</AppButton>
      </template>
    </StateBlock>

    <StateBlock
      v-else-if="freeVacancies.length === 0"
      state="empty"
      compact
      title="Офферы уже отправлены"
      text="По всем вашим активным вакансиям этот кандидат уже получил оффер. Чтобы предложить что-то ещё, заведите новую вакансию."
    >
      <template #action>
        <AppButton size="sm" variant="secondary" :to="{ name: 'employer-vacancies' }">К вакансиям</AppButton>
      </template>
    </StateBlock>

    <form v-else ref="formRef" class="offer__form" novalidate @submit.prevent="askConfirmation">
      <AppSelect
        v-model="vacancyId"
        :options="vacancyOptions"
        label="Вакансия"
        placeholder="Выберите вакансию"
        required
        :error="errors.vacancy_id"
      />

      <div class="offer__salary">
        <AppInput
          v-model="salary"
          type="number"
          label="Зарплата"
          suffix="₽"
          placeholder="Например, 150000"
          required
          :min="1"
          :step="5000"
          inputmode="numeric"
          :hint="salaryHint"
          :error="errors.salary"
          @enter="askConfirmation"
        />
        <div v-if="quickValues.length > 0" class="offer__quick" role="group" aria-label="Подставить сумму">
          <button v-for="item in quickValues" :key="item.key" type="button" class="quick" @click="salary = item.value">
            {{ item.label }}
            <span class="num">{{ formatMoney(item.value) }}</span>
          </button>
        </div>
        <p v-if="salaryNote" class="callout" :class="`callout--${salaryNote.tone}`" role="status">
          <AppIcon :name="salaryNote.tone === 'warning' ? 'alert' : 'info'" :size="16" />
          <span>{{ salaryNote.text }}</span>
        </p>
      </div>

      <AppTextarea
        v-model="message"
        label="Сообщение кандидату"
        placeholder="Чем вас заинтересовал профиль, что за команда и задачи"
        :rows="4"
        :maxlength="MAX_MESSAGE"
        hint="Необязательно, но на живое сообщение отвечают охотнее. Контактами вы обменяетесь автоматически, когда кандидат примет оффер: вставлять их в текст не нужно."
        :error="errors.message"
      />

      <AppButton type="submit" block>
        <AppIcon name="arrow-right" :size="18" />
        Отправить оффер
      </AppButton>
    </form>

    <ConfirmModal
      v-model="confirmOpen"
      title="Отправить оффер?"
      :message="confirmText"
      confirm-label="Отправить"
      :loading="busy"
      @confirm="send"
    />
  </section>
</template>

<style scoped>
.offer {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  border-color: var(--c-primary-soft-2);
  scroll-margin-top: 96px;
}
.offer__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.offer__title {
  font-size: var(--fs-lg);
}
.offer__lead {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  line-height: 1.5;
}
.offer__form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.offer__salary {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.offer__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.quick {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-height: 34px;
  padding: 5px 12px;
  border: 1px dashed var(--c-border-strong);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--c-text-muted);
  font-size: var(--fs-xs);
  font-weight: 500;
}
.quick .num {
  font-weight: 600;
  color: var(--c-ink);
}
.quick:hover {
  border-color: var(--c-primary);
  border-style: solid;
  color: var(--c-primary);
}
.callout--info {
  background: var(--c-surface-2);
}
</style>
