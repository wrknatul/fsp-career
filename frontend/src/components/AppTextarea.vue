<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    label?: string
    placeholder?: string
    hint?: string
    error?: string
    rows?: number
    /** Enables the "12 / 500" counter and the native limit. */
    maxlength?: number
    required?: boolean
    disabled?: boolean
    name?: string
  }>(),
  { rows: 4 },
)

const model = defineModel<string>({ default: '' })

const id = useId()
const describedBy = computed(() => {
  if (props.error) return `${id}-error`
  if (props.hint) return `${id}-hint`
  return undefined
})

function onInput(event: Event): void {
  model.value = (event.target as HTMLTextAreaElement).value
}
</script>

<template>
  <div class="field" :class="{ 'field--error': error }">
    <label v-if="label" class="field__label" :for="id">
      {{ label }}<span v-if="required" class="field__required" aria-hidden="true">*</span>
    </label>
    <textarea
      :id="id"
      class="field__control textarea"
      :value="model"
      :rows="rows"
      :name="name"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :required="required"
      :disabled="disabled"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="describedBy"
      @input="onInput"
    ></textarea>
    <div class="textarea__foot">
      <p v-if="error" :id="`${id}-error`" class="field__error" role="alert">{{ error }}</p>
      <p v-else-if="hint" :id="`${id}-hint`" class="field__hint">{{ hint }}</p>
      <span v-if="maxlength" class="textarea__count num" :class="{ 'is-full': model.length >= maxlength }">
        {{ model.length }} / {{ maxlength }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.textarea {
  resize: vertical;
  min-height: 96px;
}
.textarea__foot {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-3);
}
.textarea__count {
  margin-left: auto;
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  white-space: nowrap;
}
.textarea__count.is-full {
  color: var(--c-danger-text);
}
</style>
