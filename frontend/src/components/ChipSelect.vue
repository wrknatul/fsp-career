<script setup lang="ts" generic="T extends string | number">
import { useId } from 'vue'

type Option = { value: T; label: string }

// Toggle chips for small closed sets (stacks, grades, work formats...).
//   <ChipSelect v-model="form.work_formats" :options="reference.workFormatOptions" label="Формат работы" />
// Always works with an array. `single` keeps at most one selected value (clicking it again clears).
const props = withDefaults(
  defineProps<{
    options: readonly Option[]
    label?: string
    hint?: string
    error?: string
    single?: boolean
    disabled?: boolean
  }>(),
  { single: false, disabled: false },
)

const model = defineModel<T[]>({ required: true })

const id = useId()

function isOn(value: T): boolean {
  return model.value.includes(value)
}

function toggle(value: T): void {
  if (props.disabled) {
    return
  }
  if (props.single) {
    model.value = isOn(value) ? [] : [value]
    return
  }
  model.value = isOn(value) ? model.value.filter((item) => item !== value) : [...model.value, value]
}
</script>

<template>
  <div class="field" :class="{ 'field--error': error }" role="group" :aria-labelledby="label ? `${id}-label` : undefined">
    <span v-if="label" :id="`${id}-label`" class="field__label">{{ label }}</span>
    <div class="chips">
      <button
        v-for="option in options"
        :key="String(option.value)"
        type="button"
        class="chip"
        :class="{ 'is-on': isOn(option.value) }"
        :aria-pressed="isOn(option.value)"
        :disabled="disabled"
        @click="toggle(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
    <p v-if="error" class="field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" class="field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  min-height: 38px;
  padding: 7px 14px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  background: var(--c-surface);
  color: var(--c-text);
  font-size: var(--fs-sm);
  font-weight: 500;
  line-height: 1.3;
  transition:
    background var(--t-fast) var(--ease),
    border-color var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease);
}
.chip:hover:not(:disabled):not(.is-on) {
  border-color: var(--c-primary);
  color: var(--c-primary);
}
.chip.is-on {
  background: var(--c-primary-soft);
  border-color: var(--c-primary);
  color: var(--c-primary);
  font-weight: 600;
}
.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
