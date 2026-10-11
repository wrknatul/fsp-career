<script setup lang="ts">
import { computed } from 'vue'

import { formatScore } from '@/utils/format'

// Match score 0..100 as a ring. `null` (no skills and no text in the query) draws an empty ring with a dash.
const props = withDefaults(
  defineProps<{
    value: number | null
    /** Diameter in px. */
    size?: number
    /** Small caption under the number inside the ring, e.g. "из 100". */
    caption?: string
  }>(),
  { size: 72 },
)

const RADIUS = 42
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const clamped = computed(() => (props.value === null ? 0 : Math.min(100, Math.max(0, props.value))))
const dashOffset = computed(() => CIRCUMFERENCE * (1 - clamped.value / 100))
const text = computed(() => {
  if (props.value === null) {
    return '—'
  }
  return Number.isInteger(props.value) ? String(props.value) : formatScore(props.value)
})
const label = computed(() => (props.value === null ? 'Оценка не рассчитана' : `Оценка ${text.value} из 100`))
const fontSize = computed(() => `${Math.round(props.size * (text.value.length > 3 ? 0.24 : 0.3))}px`)
</script>

<template>
  <div class="ring" :style="{ width: `${size}px`, height: `${size}px` }" role="img" :aria-label="label">
    <svg viewBox="0 0 100 100" class="ring__svg" aria-hidden="true">
      <circle class="ring__track" cx="50" cy="50" :r="RADIUS" />
      <circle
        v-if="value !== null"
        class="ring__fill"
        cx="50"
        cy="50"
        :r="RADIUS"
        :stroke-dasharray="CIRCUMFERENCE"
        :stroke-dashoffset="dashOffset"
      />
    </svg>
    <div class="ring__center">
      <span class="ring__value num" :class="{ 'is-empty': value === null }" :style="{ fontSize }">{{ text }}</span>
      <span v-if="caption && value !== null" class="ring__caption">{{ caption }}</span>
    </div>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  flex: none;
}
.ring__svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.ring__track,
.ring__fill {
  fill: none;
  stroke-width: 9;
}
.ring__track {
  stroke: var(--c-border);
}
.ring__fill {
  stroke: var(--c-primary);
  stroke-linecap: round;
  transition: stroke-dashoffset 600ms var(--ease);
}
.ring__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.ring__value {
  font-weight: 700;
  color: var(--c-ink);
}
.ring__value.is-empty {
  color: var(--c-placeholder);
}
.ring__caption {
  margin-top: 2px;
  font-size: 0.625rem;
  color: var(--c-text-muted);
}
</style>
