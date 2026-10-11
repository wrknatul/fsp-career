<script setup lang="ts" generic="T extends string | number | null">
import { computed, ref, useId } from 'vue'

type InputType = 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' | 'date' | 'search'

const props = withDefaults(
  defineProps<{
    label?: string
    type?: InputType
    placeholder?: string
    hint?: string
    /** Error text under the field; also paints the border red. */
    error?: string
    required?: boolean
    disabled?: boolean
    readonly?: boolean
    autocomplete?: string
    name?: string
    inputmode?: 'text' | 'numeric' | 'decimal' | 'tel' | 'email' | 'url' | 'search'
    maxlength?: number
    min?: number | string
    max?: number | string
    step?: number | string
    /** Short unit shown inside the field on the right, e.g. "₽". */
    suffix?: string
  }>(),
  { type: 'text' },
)

// T is inferred from v-model: string for text-like fields, number | null for type="number"
// (an emptied number field becomes null).
const model = defineModel<T>({ required: true })

const emit = defineEmits<{ blur: [event: FocusEvent]; enter: [] }>()

const id = useId()
const describedBy = computed(() => {
  const ids: string[] = []
  if (props.error) ids.push(`${id}-error`)
  else if (props.hint) ids.push(`${id}-hint`)
  return ids.length > 0 ? ids.join(' ') : undefined
})

const inputRef = ref<HTMLInputElement | null>(null)

function onInput(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  if (props.type === 'number') {
    model.value = (value === '' ? null : Number(value)) as T
  } else {
    model.value = value as T
  }
}

defineExpose({ focus: () => inputRef.value?.focus() })
</script>

<template>
  <div class="field" :class="{ 'field--error': error }">
    <label v-if="label" class="field__label" :for="id">
      {{ label }}<span v-if="required" class="field__required" aria-hidden="true">*</span>
    </label>
    <div class="input-wrap">
      <input
        :id="id"
        ref="inputRef"
        class="field__control"
        :class="{ 'has-suffix': suffix }"
        :type="type"
        :value="model ?? ''"
        :name="name"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :readonly="readonly"
        :autocomplete="autocomplete"
        :inputmode="inputmode"
        :maxlength="maxlength"
        :min="min"
        :max="max"
        :step="step"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        @input="onInput"
        @blur="emit('blur', $event)"
        @keydown.enter="emit('enter')"
      />
      <span v-if="suffix" class="input-wrap__suffix" aria-hidden="true">{{ suffix }}</span>
    </div>
    <p v-if="error" :id="`${id}-error`" class="field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.input-wrap {
  position: relative;
  display: flex;
}
.has-suffix {
  padding-right: 40px;
}
.input-wrap__suffix {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-family: var(--font-mono);
  color: var(--c-text-muted);
  pointer-events: none;
}
/* Hide native number spinners: they clash with the design and are awkward on touch. */
input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}
input[type='number']::-webkit-outer-spin-button,
input[type='number']::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
</style>
