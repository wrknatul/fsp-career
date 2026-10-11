<script setup lang="ts" generic="T extends string | number">
import { useId } from 'vue'

type Option = { value: T; label: string }

// Two or three mutually exclusive options as a pill switch (role switch, view mode...).
//   <SegmentedControl v-model="role" :options="[{ value: 'candidate', label: 'Соискатель' }, ...]" label="Я" />
defineProps<{ options: readonly Option[]; label?: string; block?: boolean }>()

const model = defineModel<T>({ required: true })

const id = useId()
</script>

<template>
  <div class="seg-wrap">
    <span v-if="label" :id="`${id}-label`" class="field__label">{{ label }}</span>
    <div class="seg" :class="{ 'seg--block': block }" role="radiogroup" :aria-labelledby="label ? `${id}-label` : undefined">
      <button
        v-for="option in options"
        :key="String(option.value)"
        type="button"
        role="radio"
        class="seg__item"
        :class="{ 'is-on': model === option.value }"
        :aria-checked="model === option.value"
        @click="model = option.value"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.seg-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.seg {
  display: inline-flex;
  padding: 4px;
  gap: 4px;
  border-radius: var(--r-md);
  background: var(--c-neutral-soft);
}
.seg--block {
  display: flex;
}
.seg--block .seg__item {
  flex: 1;
}
.seg__item {
  min-height: 38px;
  padding: 8px 16px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--c-text-muted);
  font-size: 0.9375rem;
  font-weight: 600;
  transition:
    background var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease),
    box-shadow var(--t-fast) var(--ease);
}
.seg__item:hover:not(.is-on) {
  color: var(--c-ink);
}
.seg__item.is-on {
  background: var(--c-surface);
  color: var(--c-ink);
  box-shadow: var(--shadow-sm);
}
</style>
