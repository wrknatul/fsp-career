<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { fieldErrors, getErrorMessage, hasErrorCode } from '@/api/client'
import type { Role } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppInput from '@/components/AppInput.vue'
import AuthCard from '@/components/AuthCard.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import { useAuthStore } from '@/stores/auth'
import { DEMO_MODE, demoAccount } from '@/utils/demo'
import { safeRedirect } from '@/utils/redirect'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'candidate', label: 'Соискатель' },
  { value: 'employer', label: 'Работодатель' },
]

// The role switch only picks which demo account to fill in; the server decides the real role.
const role = ref<Role>('candidate')
const form = reactive({ email: '', password: '' })
const errors = reactive({ email: '', password: '', form: '' })
const submitting = ref(false)

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function clearErrors(): void {
  errors.email = ''
  errors.password = ''
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
  if (form.password === '') {
    errors.password = 'Введите пароль'
  }
  return errors.email === '' && errors.password === ''
}

async function submit(): Promise<void> {
  if (!validate()) {
    return
  }
  submitting.value = true
  try {
    const user = await auth.login({ email: form.email.trim(), password: form.password })
    await router.push(safeRedirect(route.query.redirect, user.role))
  } catch (err) {
    if (hasErrorCode(err, 'INVALID_CREDENTIALS')) {
      errors.form = 'Неверная почта или пароль. Проверьте раскладку и попробуйте ещё раз.'
    } else {
      const fields = fieldErrors(err)
      errors.email = fields.email ?? ''
      errors.password = fields.password ?? ''
      if (errors.email === '' && errors.password === '') {
        errors.form = getErrorMessage(err)
      }
    }
  } finally {
    submitting.value = false
  }
}

function fillDemo(): void {
  const account = demoAccount(role.value)
  form.email = account.email
  form.password = account.password
  clearErrors()
}
</script>

<template>
  <AuthCard title="Вход" subtitle="Войдите, чтобы продолжить работу с профилем или поиском.">
    <form class="form" novalidate @submit.prevent="submit">
      <SegmentedControl v-model="role" :options="ROLE_OPTIONS" label="Я" block />

      <AppInput
        v-model="form.email"
        label="Почта"
        type="email"
        name="email"
        autocomplete="username"
        inputmode="email"
        placeholder="name@example.com"
        :error="errors.email"
      />
      <AppInput
        v-model="form.password"
        label="Пароль"
        type="password"
        name="password"
        autocomplete="current-password"
        :error="errors.password"
      />

      <p v-if="errors.form" class="callout callout--danger" role="alert">
        <AppIcon name="alert" :size="16" />
        <span>{{ errors.form }}</span>
      </p>

      <AppButton type="submit" size="lg" block :loading="submitting">Войти</AppButton>
    </form>

    <div v-if="DEMO_MODE" class="demo callout callout--primary">
      <AppIcon name="info" :size="18" />
      <div class="demo__body">
        <p class="demo__title">Демо-доступ</p>
        <p class="demo__text">
          Почта <span class="mono">{{ demoAccount(role).email }}</span>, пароль
          <span class="mono">{{ demoAccount(role).password }}</span>
        </p>
        <AppButton variant="secondary" size="sm" @click="fillDemo">Подставить в форму</AppButton>
      </div>
    </div>

    <template #footer>
      Нет аккаунта? <RouterLink :to="{ name: 'register' }" class="link">Зарегистрироваться</RouterLink>
    </template>
  </AuthCard>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.demo {
  font-size: var(--fs-sm);
}
.demo :deep(svg) {
  margin-top: 2px;
  color: var(--c-primary);
}
.demo__body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-2);
  min-width: 0;
}
.demo__title {
  font-family: var(--font-mono);
  font-weight: 600;
}
.demo__text {
  overflow-wrap: anywhere;
  color: var(--c-text-muted);
}
.demo .mono {
  color: var(--c-ink);
  font-size: var(--fs-xs);
}
</style>
