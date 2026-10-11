<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import { useReferenceStore } from '@/stores/reference'

import AppIcon from './AppIcon.vue'

// Multi-select of skills from the dictionary with search. The model is a list of skill ids.
//   <SkillPicker v-model="query.skills_required" label="Обязательные навыки" :exclude="query.skills_optional" />
const props = withDefaults(
  defineProps<{
    label?: string
    placeholder?: string
    hint?: string
    error?: string
    /** Ids that must not be offered (e.g. already chosen in the sibling list). */
    exclude?: readonly string[]
    disabled?: boolean
    maxSuggestions?: number
  }>(),
  { placeholder: 'Начните вводить: Python, Docker…', exclude: () => [], disabled: false, maxSuggestions: 8 },
)

const model = defineModel<string[]>({ required: true })

const reference = useReferenceStore()
const id = useId()
const text = ref('')
const focused = ref(false)
const active = ref(0)

const suggestions = computed(() => {
  const needle = text.value.trim().toLowerCase()
  const taken = new Set([...model.value, ...props.exclude])
  return reference.skillOptions
    .filter((option) => !taken.has(option.value))
    .filter((option) => needle === '' || option.label.toLowerCase().includes(needle) || option.value.includes(needle))
    .slice(0, props.maxSuggestions)
})

const isOpen = computed(() => focused.value && !props.disabled && suggestions.value.length > 0)

function add(skillId: string): void {
  if (!model.value.includes(skillId)) {
    model.value = [...model.value, skillId]
  }
  text.value = ''
  active.value = 0
}

function remove(skillId: string): void {
  model.value = model.value.filter((item) => item !== skillId)
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    active.value = Math.min(active.value + 1, suggestions.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    active.value = Math.max(active.value - 1, 0)
  } else if (event.key === 'Enter') {
    const choice = suggestions.value[active.value]
    if (choice !== undefined && isOpen.value) {
      event.preventDefault()
      add(choice.value)
    }
  } else if (event.key === 'Escape') {
    focused.value = false
  } else if (event.key === 'Backspace' && text.value === '' && model.value.length > 0) {
    remove(model.value[model.value.length - 1])
  }
}

function onInput(event: Event): void {
  text.value = (event.target as HTMLInputElement).value
  active.value = 0
}

function onBlur(): void {
  // Delay: a click on a suggestion must register before the list disappears.
  window.setTimeout(() => {
    focused.value = false
  }, 120)
}
</script>

<template>
  <div class="field" :class="{ 'field--error': error }">
    <label v-if="label" class="field__label" :for="id">{{ label }}</label>

    <div class="picker-wrap">
      <div class="picker" :class="{ 'is-focused': focused, 'is-disabled': disabled }">
        <ul v-if="model.length > 0" class="picker__chosen" aria-label="Выбранные навыки">
          <li v-for="skillId in model" :key="skillId" class="picker__tag">
            {{ reference.skillTitle(skillId) }}
            <button
              type="button"
              class="picker__remove"
              :aria-label="`Убрать навык ${reference.skillTitle(skillId)}`"
              :disabled="disabled"
              @click="remove(skillId)"
            >
              <AppIcon name="x" :size="12" />
            </button>
          </li>
        </ul>
        <input
          :id="id"
          class="picker__input"
          type="text"
          autocomplete="off"
          role="combobox"
          aria-autocomplete="list"
          :aria-expanded="isOpen"
          :aria-controls="`${id}-list`"
          :placeholder="model.length === 0 ? placeholder : 'Ещё навык…'"
          :value="text"
          :disabled="disabled"
          @input="onInput"
          @focus="focused = true"
          @blur="onBlur"
          @keydown="onKeydown"
        />
      </div>

      <ul v-show="isOpen" :id="`${id}-list`" class="picker__list" role="listbox">
        <li
          v-for="(option, index) in suggestions"
          :key="option.value"
          class="picker__option"
          :class="{ 'is-active': index === active }"
          role="option"
          :aria-selected="index === active"
          @mousedown.prevent="add(option.value)"
          @mousemove="active = index"
        >
          {{ option.label }}
        </li>
      </ul>
    </div>

    <p v-if="error" class="field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" class="field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.picker-wrap {
  position: relative;
}
.picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 6px 10px;
  background: var(--c-surface);
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  transition:
    border-color var(--t-fast) var(--ease),
    box-shadow var(--t-fast) var(--ease);
}
.picker.is-focused {
  border-color: var(--c-primary);
  box-shadow: var(--ring);
}
.picker.is-disabled {
  background: var(--c-surface-2);
}
.field--error .picker {
  border-color: var(--c-danger);
}
.picker__chosen {
  display: contents;
  list-style: none;
}
.picker__tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 4px 3px 10px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 600;
}
.picker__remove {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: inherit;
}
.picker__remove:hover:not(:disabled) {
  background: var(--c-primary-soft-2);
}
.picker__input {
  flex: 1;
  min-width: 140px;
  padding: 6px 4px;
  border: 0;
  outline: none;
  background: transparent;
  font-size: var(--fs-base);
}
.picker__input::placeholder {
  color: var(--c-placeholder);
}
.picker__list {
  position: absolute;
  z-index: 30;
  left: 0;
  right: 0;
  margin-top: 4px;
  top: 100%;
  max-height: 280px;
  overflow-y: auto;
  list-style: none;
  padding: 6px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-md);
}
.picker__option {
  padding: 9px 12px;
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
  cursor: pointer;
}
.picker__option.is-active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
</style>
