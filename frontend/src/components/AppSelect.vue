<script setup lang="ts" generic="T extends string | number">
import { computed, useId } from 'vue'

type Option = { value: T; label: string; disabled?: boolean }

const props = defineProps<{
  options: readonly Option[]
  label?: string
  /** Adds an empty first option with this text; choosing it sets the model to null. */
  placeholder?: string
  hint?: string
  error?: string
  required?: boolean
  disabled?: boolean
  name?: string
}>()

// T | null: the model is null while nothing is chosen.
const model = defineModel<T | null>({ required: true })

const id = useId()
const describedBy = computed(() => {
  if (props.error) return `${id}-error`
  if (props.hint) return `${id}-hint`
  return undefined
})

function onChange(event: Event): void {
  const raw = (event.target as HTMLSelectElement).value
  if (raw === '') {
    model.value = null
    return
  }
  // The DOM only knows strings: map back to the original option value (number or string).
  const found = props.options.find((option) => String(option.value) === raw)
  model.value = found === undefined ? null : found.value
}
</script>

<template>
  <div class="field" :class="{ 'field--error': error }">
    <label v-if="label" class="field__label" :for="id">
      {{ label }}<span v-if="required" class="field__required" aria-hidden="true">*</span>
    </label>
    <select
      :id="id"
      class="field__control select"
      :value="model === null ? '' : String(model)"
      :name="name"
      :required="required"
      :disabled="disabled"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="describedBy"
      @change="onChange"
    >
      <option v-if="placeholder !== undefined" value="">{{ placeholder }}</option>
      <option
        v-for="option in options"
        :key="String(option.value)"
        :value="String(option.value)"
        :disabled="option.disabled"
      >
        {{ option.label }}
      </option>
    </select>
    <p v-if="error" :id="`${id}-error`" class="field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.select {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 40px;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%235e5f66' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
}
</style>
