<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { patchProfile } from '@/api/candidate'
import { fieldErrors, hasErrorCode } from '@/api/client'
import type { CandidateProfile, ProfilePatch, WorkFormat } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppCheckbox from '@/components/AppCheckbox.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppInput from '@/components/AppInput.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTextarea from '@/components/AppTextarea.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'

// The questionnaire: identity (locked while FSP is linked), city, work formats, salary, about, contacts.
const props = defineProps<{ profile: CandidateProfile }>()
const emit = defineEmits<{ saved: [profile: CandidateProfile] }>()

const reference = useReferenceStore()
const toast = useToastStore()
const auth = useAuthStore()

type FormState = {
  full_name: string
  birth_date: string
  city: string | null
  work_formats: WorkFormat[]
  relocation: boolean
  salary: number | null
  about: string
  telegram: string
  phone: string
}

type Normalized = Required<Omit<ProfilePatch, 'visible'>>

const MAX_SALARY = 100_000_000
const MIN_BIRTH_DATE = '1900-01-01'

function fromProfile(profile: CandidateProfile): FormState {
  return {
    full_name: profile.user.full_name,
    birth_date: profile.birth_date ?? '',
    city: profile.city,
    work_formats: [...profile.work_formats],
    relocation: profile.relocation,
    salary: profile.salary_expectation,
    about: profile.about ?? '',
    telegram: profile.telegram ?? '',
    phone: profile.phone ?? '',
  }
}

function blankToNull(value: string): string | null {
  const text = value.trim()
  return text === '' ? null : text
}

function normalize(state: FormState): Normalized {
  return {
    full_name: state.full_name.trim(),
    birth_date: blankToNull(state.birth_date),
    city: state.city === null ? null : blankToNull(state.city),
    work_formats: [...state.work_formats],
    relocation: state.relocation,
    salary_expectation: state.salary,
    about: blankToNull(state.about),
    telegram: blankToNull(state.telegram),
    phone: blankToNull(state.phone),
  }
}

function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

const form = reactive<FormState>(fromProfile(props.profile))
const errors = reactive<Record<string, string>>({})
const saving = ref(false)

const locked = computed(() => props.profile.fsp !== null)

// A new profile (e.g. the resume filled the city) updates only the fields the user has not touched.
function adopt<K extends keyof FormState>(key: K, before: FormState, after: FormState): void {
  if (sameValue(form[key], before[key])) {
    form[key] = after[key]
  }
}

watch(
  () => props.profile,
  (next, prev) => {
    const before = fromProfile(prev)
    const after = fromProfile(next)
    adopt('full_name', before, after)
    adopt('birth_date', before, after)
    adopt('city', before, after)
    adopt('work_formats', before, after)
    adopt('relocation', before, after)
    adopt('salary', before, after)
    adopt('about', before, after)
    adopt('telegram', before, after)
    adopt('phone', before, after)
  },
)

/** Only the fields the user changed; identity fields are never sent while FSP is linked. */
function buildPatch(): ProfilePatch {
  const now = normalize(form)
  const base = normalize(fromProfile(props.profile))
  const patch: ProfilePatch = {}
  if (!locked.value) {
    if (now.full_name !== base.full_name) patch.full_name = now.full_name
    if (now.birth_date !== base.birth_date) patch.birth_date = now.birth_date
  }
  if (now.city !== base.city) patch.city = now.city
  if (!sameValue(now.work_formats, base.work_formats)) patch.work_formats = now.work_formats
  if (now.relocation !== base.relocation) patch.relocation = now.relocation
  if (now.salary_expectation !== base.salary_expectation) patch.salary_expectation = now.salary_expectation
  if (now.about !== base.about) patch.about = now.about
  if (now.telegram !== base.telegram) patch.telegram = now.telegram
  if (now.phone !== base.phone) patch.phone = now.phone
  return patch
}

const dirty = computed(() => Object.keys(buildPatch()).length > 0)

function clearErrors(): void {
  for (const key of Object.keys(errors)) {
    delete errors[key]
  }
}

function todayIso(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function validate(patch: ProfilePatch): boolean {
  clearErrors()
  if (patch.full_name !== undefined && patch.full_name === '') {
    errors.full_name = 'Укажите ФИО'
  }
  if (patch.birth_date !== undefined && patch.birth_date !== null) {
    if (patch.birth_date < MIN_BIRTH_DATE || patch.birth_date > todayIso()) {
      errors.birth_date = 'Проверьте дату рождения'
    }
  }
  if (patch.salary_expectation !== undefined && patch.salary_expectation !== null) {
    const value = patch.salary_expectation
    if (!Number.isInteger(value) || value < 1 || value > MAX_SALARY) {
      errors.salary = 'Введите целую сумму в рублях, от 1 до 100 000 000'
    }
  }
  return Object.keys(errors).length === 0
}

async function save(): Promise<void> {
  if (saving.value) {
    return
  }
  const patch = buildPatch()
  if (Object.keys(patch).length === 0) {
    return
  }
  if (!validate(patch)) {
    return
  }
  saving.value = true
  try {
    const next = await patchProfile(patch)
    emit('saved', next)
    if (patch.full_name !== undefined) {
      auth.setUser(next.user)
    }
    toast.success('Анкета сохранена')
  } catch (err) {
    const fields = fieldErrors(err)
    const known: Record<string, string> = { salary_expectation: 'salary' }
    let shown = false
    for (const [field, message] of Object.entries(fields)) {
      errors[known[field] ?? field] = message
      shown = true
    }
    if (!shown || hasErrorCode(err, 'FSP_LINKED_LOCKED')) {
      toast.fromError(err)
    }
  } finally {
    saving.value = false
  }
}

function reset(): void {
  Object.assign(form, fromProfile(props.profile))
  clearErrors()
}

// City: a dictionary select keeps spelling consistent with employer filters; the current value is always listed.
const cityOptions = computed(() => {
  const options = [...reference.cityOptions]
  if (form.city !== null && form.city !== '' && !options.some((option) => option.value === form.city)) {
    options.unshift({ value: form.city, label: form.city })
  }
  return options
})
const hasCityList = computed(() => reference.cities.length > 0)
</script>

<template>
  <section id="questionnaire" class="card q" aria-labelledby="q-title">
    <header class="q__head">
      <h2 id="q-title" class="h3">Анкета</h2>
      <p class="q__sub">То, что вы указываете сами. Это не подтверждение: в индекс анкета не входит.</p>
    </header>

    <form class="q__form" novalidate @submit.prevent="save">
      <div v-if="locked" class="callout callout--primary">
        <AppIcon name="lock" :size="16" />
        <span>
          ФИО и дата рождения совпадают с реестром ФСП и заблокированы, пока ФСП привязан.
          <RouterLink to="/candidate/fsp" class="link">Перейти к привязке</RouterLink>
        </span>
      </div>

      <div class="q__grid">
        <AppInput
          v-model="form.full_name"
          label="ФИО"
          required
          autocomplete="name"
          :maxlength="200"
          :disabled="locked"
          :error="errors.full_name"
        />
        <AppInput
          v-model="form.birth_date"
          label="Дата рождения"
          type="date"
          autocomplete="bday"
          min="1900-01-01"
          :disabled="locked"
          :error="errors.birth_date"
          :hint="locked ? undefined : 'Нужна для сверки с реестром ФСП. Работодатель её не видит.'"
        />
      </div>

      <div class="q__grid">
        <AppSelect
          v-if="hasCityList"
          v-model="form.city"
          label="Город"
          placeholder="Не выбран"
          :options="cityOptions"
          :error="errors.city"
        />
        <AppInput
          v-else
          :model-value="form.city ?? ''"
          label="Город"
          :maxlength="100"
          :error="errors.city"
          @update:model-value="form.city = $event"
        />
        <AppInput
          v-model="form.salary"
          label="Зарплатные ожидания"
          type="number"
          suffix="₽"
          inputmode="numeric"
          min="1"
          step="1000"
          hint="В месяц, в рублях. Работодатель видит эту сумму до оффера."
          :error="errors.salary"
        />
      </div>

      <ChipSelect
        v-model="form.work_formats"
        :options="reference.workFormatOptions"
        label="Формат работы"
        hint="Можно выбрать несколько. По ним работодатель отбирает кандидатов."
        :error="errors.work_formats"
      />

      <AppCheckbox v-model="form.relocation" label="Готов к переезду" hint="Тогда город не станет препятствием в поиске." />

      <AppTextarea
        v-model="form.about"
        label="О себе"
        :rows="5"
        :maxlength="2000"
        :error="errors.about"
        hint="Контакты из этого текста будут скрыты до оффера: почта, телефон, @ники и ссылки заменятся на «[скрыто]». Напишите о задачах и опыте, а контакты оставьте в полях ниже."
      />

      <div class="q__grid">
        <AppInput
          v-model="form.telegram"
          label="Telegram"
          placeholder="@username"
          :maxlength="64"
          autocomplete="off"
          :error="errors.telegram"
          hint="Откроется работодателю только после принятого оффера."
        />
        <AppInput
          v-model="form.phone"
          label="Телефон"
          type="tel"
          placeholder="+7 900 000-00-00"
          :maxlength="32"
          autocomplete="tel"
          :error="errors.phone"
          hint="Откроется работодателю только после принятого оффера."
        />
      </div>

      <div class="q__actions">
        <AppButton type="submit" :loading="saving" :disabled="!dirty">Сохранить анкету</AppButton>
        <AppButton v-if="dirty && !saving" variant="ghost" @click="reset">Сбросить изменения</AppButton>
        <span v-if="!dirty" class="q__saved text-sm muted">Изменений нет</span>
      </div>
    </form>
  </section>
</template>

<style scoped>
.q {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  scroll-margin-top: 80px;
}
.q__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.q__sub {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  line-height: 1.5;
}
.q__form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.q__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
}
.q__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
}

@media (min-width: 560px) {
  .q__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
