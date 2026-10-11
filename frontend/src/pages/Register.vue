<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { fieldErrors, getErrorMessage, hasErrorCode } from '@/api/client'
import type { RegisterRequest, Role } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppCheckbox from '@/components/AppCheckbox.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppInput from '@/components/AppInput.vue'
import AuthCard from '@/components/AuthCard.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'candidate', label: 'Соискатель' },
  { value: 'employer', label: 'Работодатель' },
]

const role = ref<Role>('candidate')
const form = reactive({
  email: '',
  password: '',
  full_name: '',
  company_name: '',
  consent: false,
  show_profile: false,
})
const errors = reactive({
  email: '',
  password: '',
  full_name: '',
  company_name: '',
  consent: '',
  form: '',
})
const submitting = ref(false)

const isCandidate = computed(() => role.value === 'candidate')
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_MIN_BYTES = 8
const PASSWORD_MAX_BYTES = 72
// Server limits (RegisterRequest): full_name and company_name up to 200 characters, e-mail up to 254.
const MAX_NAME_LENGTH = 200
const MAX_EMAIL_LENGTH = 254

function clearErrors(): void {
  errors.email = ''
  errors.password = ''
  errors.full_name = ''
  errors.company_name = ''
  errors.consent = ''
  errors.form = ''
}

function validate(): boolean {
  clearErrors()
  const email = form.email.trim()
  if (email === '') {
    errors.email = 'Введите почту'
  } else if (!EMAIL_PATTERN.test(email)) {
    errors.email = 'Похоже, в адресе опечатка'
  }

  // The server counts bytes (bcrypt limit): Cyrillic letters take two bytes each.
  const bytes = new TextEncoder().encode(form.password).length
  if (bytes < PASSWORD_MIN_BYTES) {
    errors.password = 'Пароль короче 8 символов'
  } else if (bytes > PASSWORD_MAX_BYTES) {
    errors.password = 'Пароль слишком длинный: максимум 72 байта (кириллица занимает по 2 байта на букву)'
  }

  if (form.full_name.trim().length < 2) {
    errors.full_name = isCandidate.value ? 'Введите фамилию, имя и отчество' : 'Введите ваше имя'
  }
  if (!isCandidate.value && form.company_name.trim() === '') {
    errors.company_name = 'Укажите название компании'
  }
  if (!form.consent) {
    errors.consent = 'Без согласия на обработку данных создать аккаунт нельзя'
  }
  return Object.entries(errors).every(([key, value]) => key === 'form' || value === '')
}

function buildRequest(): RegisterRequest {
  const request: RegisterRequest = {
    email: form.email.trim(),
    password: form.password,
    role: role.value,
    full_name: form.full_name.trim().replace(/\s+/g, ' '),
    consent: true,
  }
  if (isCandidate.value) {
    request.show_profile = form.show_profile
  } else {
    request.company_name = form.company_name.trim()
  }
  return request
}

async function submit(): Promise<void> {
  if (!validate()) {
    return
  }
  submitting.value = true
  try {
    const user = await auth.register(buildRequest())
    toast.success('Аккаунт создан. Добро пожаловать!')
    await router.push(user.role === 'employer' ? '/employer' : '/candidate')
  } catch (err) {
    if (hasErrorCode(err, 'EMAIL_TAKEN')) {
      errors.email = 'Эта почта уже зарегистрирована. Войдите или укажите другую.'
    } else if (hasErrorCode(err, 'CONSENT_REQUIRED')) {
      errors.consent = getErrorMessage(err)
    } else {
      const fields = fieldErrors(err)
      errors.email = fields.email ?? ''
      errors.password = fields.password ?? ''
      errors.full_name = fields.full_name ?? ''
      errors.company_name = fields.company_name ?? ''
      errors.consent = fields.consent ?? ''
      const hasFieldError = Object.entries(errors).some(([key, value]) => key !== 'form' && value !== '')
      if (!hasFieldError) {
        errors.form = getErrorMessage(err)
      }
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthCard
    title="Создать аккаунт"
    :subtitle="
      isCandidate
        ? 'Соберите профиль из подтверждаемых источников — работодатели найдут вас сами.'
        : 'Находите специалистов по категориям и отправляйте офферы с зарплатой.'
    "
  >
    <form class="form" novalidate @submit.prevent="submit">
      <SegmentedControl v-model="role" :options="ROLE_OPTIONS" label="Я" block />

      <AppInput
        v-model="form.full_name"
        :label="isCandidate ? 'Фамилия Имя Отчество' : 'Ваше имя'"
        name="name"
        autocomplete="name"
        :placeholder="isCandidate ? 'Смирнов Алексей Игоревич' : 'Ирина Петрова'"
        :hint="
          isCandidate
            ? 'Как в паспорте: по ФИО и дате рождения проверяется привязка к реестру ФСП. Работодатель увидит только «Алексей С.».'
            : undefined
        "
        :maxlength="MAX_NAME_LENGTH"
        :error="errors.full_name"
      />

      <AppInput
        v-if="!isCandidate"
        v-model="form.company_name"
        label="Компания"
        name="organization"
        autocomplete="organization"
        placeholder="Название компании"
        :maxlength="MAX_NAME_LENGTH"
        :error="errors.company_name"
      />

      <AppInput
        v-model="form.email"
        label="Почта"
        type="email"
        name="email"
        autocomplete="username"
        inputmode="email"
        placeholder="name@example.com"
        :maxlength="MAX_EMAIL_LENGTH"
        :error="errors.email"
      />

      <AppInput
        v-model="form.password"
        label="Пароль"
        type="password"
        name="new-password"
        autocomplete="new-password"
        hint="От 8 символов."
        :error="errors.password"
      />

      <div class="consents">
        <AppCheckbox v-model="form.consent" :error="errors.consent" name="consent">
          Согласен на обработку персональных данных. Подробности — в
          <a href="/privacy" target="_blank" rel="noopener" class="link">описании, какие данные мы собираем</a>.
        </AppCheckbox>

        <AppCheckbox
          v-if="isCandidate"
          v-model="form.show_profile"
          name="show_profile"
          hint="Можно включить или выключить позже на странице «Обзор». Пока галочки нет, вас не найдут в поиске."
        >
          Показывать мой профиль работодателям. Они увидят
          <a href="/privacy" target="_blank" rel="noopener" class="link">имя с первой буквой фамилии и профиль без контактов</a>.
        </AppCheckbox>
      </div>

      <p v-if="errors.form" class="callout callout--danger" role="alert">
        <AppIcon name="alert" :size="16" />
        <span>{{ errors.form }}</span>
      </p>

      <AppButton type="submit" size="lg" block :loading="submitting">Создать аккаунт</AppButton>
    </form>

    <template #footer>
      Уже есть аккаунт? <RouterLink :to="{ name: 'login' }" class="link">Войти</RouterLink>
    </template>
  </AuthCard>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.consents {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-surface-2);
  border: 1px solid var(--c-border);
}
</style>
