<script setup lang="ts">
import { computed } from 'vue'

import type { Verification } from '@/api/types'
import { useReferenceStore } from '@/stores/reference'
import { VERIFICATION_TITLES, VERIFICATION_WEIGHTS } from '@/utils/labels'

import AppIcon from './AppIcon.vue'

// Badge of a fact's confirmation level:
//   verified -> "Подтверждено ФСП" (filled with the brand colour; with a "демо" mark in mock mode)
//   tested   -> "Подтверждено тестом" (green)
//   parsed   -> "Из резюме" (gray)
//   declared -> "Заявлено" (outline)
const props = withDefaults(defineProps<{ verification: Verification; size?: 'sm' | 'md' }>(), { size: 'md' })

const reference = useReferenceStore()

const label = computed(() => VERIFICATION_TITLES[props.verification])
const showDemoMark = computed(() => props.verification === 'verified' && reference.isMock)
const tooltip = computed(() => {
  const weight = VERIFICATION_WEIGHTS[props.verification].toFixed(2).replace('.', ',')
  const demo = showDemoMark.value ? '. Данные реестра в демо смоделированы' : ''
  return `${label.value}. Вес доверия ${weight}${demo}`
})
</script>

<template>
  <span class="badge" :class="[`badge--${verification}`, `badge--${size}`]" :title="tooltip">
    <AppIcon v-if="verification === 'verified' || verification === 'tested'" name="check" :size="size === 'sm' ? 11 : 13" />
    <span class="badge__text">{{ label }}</span>
    <span v-if="showDemoMark" class="badge__demo">демо</span>
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border: 1px solid transparent;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
  vertical-align: middle;
}
.badge--sm {
  padding: 1px 8px;
  font-size: 0.6875rem;
}
.badge--verified {
  background: var(--c-primary);
  color: #fff;
}
.badge--tested {
  background: var(--c-success-soft);
  border-color: var(--c-success-border);
  color: var(--c-success-text);
}
.badge--parsed {
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.badge--declared {
  background: transparent;
  border-color: #8a8b93;
  color: var(--c-text-muted);
}
.badge__demo {
  margin-left: 2px;
  padding: 0 5px;
  border-radius: var(--r-pill);
  background: rgba(255, 255, 255, 0.22);
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
</style>
