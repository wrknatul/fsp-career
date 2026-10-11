<script setup lang="ts">
import { computed, useId } from 'vue'

import AppIcon from './AppIcon.vue'

const props = defineProps<{
  /** Plain-text label; use the default slot for a label with links. */
  label?: string
  hint?: string
  error?: string
  disabled?: boolean
  required?: boolean
  name?: string
}>()

const model = defineModel<boolean>({ default: false })

const id = useId()
const describedBy = computed(() => {
  if (props.error) return `${id}-error`
  if (props.hint) return `${id}-hint`
  return undefined
})

function onChange(event: Event): void {
  model.value = (event.target as HTMLInputElement).checked
}
</script>

<template>
  <div class="check" :class="{ 'check--error': error, 'check--disabled': disabled }">
    <label class="check__row">
      <input
        :id="id"
        class="check__input"
        type="checkbox"
        :checked="model"
        :name="name"
        :disabled="disabled"
        :required="required"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        @change="onChange"
      />
      <span class="check__box" aria-hidden="true"><AppIcon name="check" :size="14" /></span>
      <span class="check__label"><slot>{{ label }}</slot></span>
    </label>
    <p v-if="error" :id="`${id}-error`" class="field__error check__note" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="field__hint check__note">{{ hint }}</p>
  </div>
</template>

<style scoped>
.check {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.check__row {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}
.check--disabled .check__row {
  cursor: not-allowed;
  opacity: 0.6;
}
.check__input {
  position: absolute;
  opacity: 0;
  width: 22px;
  height: 22px;
  margin: 0;
  cursor: inherit;
}
.check__box {
  flex: none;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  margin-top: 1px;
  border: 1.5px solid #b3b3bc;
  border-radius: 6px;
  background: var(--c-surface);
  color: transparent;
  transition:
    background var(--t-fast) var(--ease),
    border-color var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease),
    box-shadow var(--t-fast) var(--ease);
}
.check__row:hover .check__input:not(:disabled) + .check__box {
  border-color: var(--c-primary);
}
.check__input:checked + .check__box {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: #fff;
}
.check__input:focus-visible + .check__box {
  box-shadow: var(--ring);
  border-color: var(--c-primary);
}
.check--error .check__box {
  border-color: var(--c-danger);
}
.check__label {
  font-size: 0.9375rem;
  line-height: 1.45;
  color: var(--c-text);
}
.check__note {
  padding-left: 34px;
}
</style>
