<script setup lang="ts">
import type { Verification } from '@/api/types'
import { VERIFICATION_TITLES } from '@/utils/labels'

// Key to the dots on skill chips (the same colours as SkillChip): what the point in front of a skill means.
const ITEMS: readonly Verification[] = ['verified', 'tested', 'parsed', 'declared']
</script>

<template>
  <p class="legend">
    <span class="legend__title">Точка у навыка:</span>
    <span v-for="item in ITEMS" :key="item" class="legend__item">
      <span class="legend__dot" :class="`legend__dot--${item}`" aria-hidden="true"></span>
      {{ VERIFICATION_TITLES[item] }}
    </span>
  </p>
</template>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.legend__title {
  font-weight: 600;
}
.legend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid var(--dot);
  background: var(--dot);
}
.legend__dot--verified {
  --dot: var(--c-primary);
}
.legend__dot--tested {
  --dot: var(--c-success);
}
.legend__dot--parsed {
  --dot: #8a8b93;
}
.legend__dot--declared {
  --dot: #8a8b93;
  background: transparent;
}
</style>
