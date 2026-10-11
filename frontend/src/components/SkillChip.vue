<script setup lang="ts">
import { computed } from 'vue'

import type { Verification } from '@/api/types'
import { VERIFICATION_TITLES } from '@/utils/labels'

// Skill with a confirmation dot and a 3-step evidence strength meter.
//   <SkillChip :title="s.title" :verification="s.verification" :evidence="s.evidence" />
// `missing` draws a dashed "requested but absent" chip (no dot, no meter).
const props = withDefaults(
  defineProps<{
    title: string
    verification?: Verification | null
    /** Evidence strength 0..1 (SkillEvidence.evidence). */
    evidence?: number | null
    missing?: boolean
  }>(),
  { verification: null, evidence: null, missing: false },
)

const steps = computed(() => {
  if (props.evidence === null) {
    return 0
  }
  if (props.evidence >= 0.67) return 3
  if (props.evidence >= 0.34) return 2
  return 1
})

const tooltip = computed(() => {
  if (props.missing) {
    return `${props.title}: у кандидата нет подтверждения этого навыка`
  }
  const parts = [props.title]
  if (props.verification !== null) {
    parts.push(VERIFICATION_TITLES[props.verification])
  }
  if (props.evidence !== null) {
    parts.push(`сила свидетельства ${props.evidence.toFixed(2).replace('.', ',')}`)
  }
  return parts.join(' · ')
})
</script>

<template>
  <span class="chip" :class="[{ 'chip--missing': missing }, verification ? `chip--${verification}` : '']" :title="tooltip">
    <span v-if="!missing && verification" class="chip__dot" aria-hidden="true"></span>
    <span class="chip__title">{{ title }}</span>
    <span v-if="!missing && evidence !== null" class="chip__meter" aria-hidden="true">
      <span v-for="step in 3" :key="step" class="chip__bar" :class="{ 'is-on': step <= steps }"></span>
    </span>
    <span class="sr-only">
      <template v-if="missing">, нет подтверждения</template>
      <template v-else>
        <template v-if="verification">, {{ VERIFICATION_TITLES[verification] }}</template>
        <template v-if="evidence !== null">, сила {{ Math.round(evidence * 100) }} из 100</template>
      </template>
    </span>
  </span>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px 4px 9px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  background: var(--c-surface);
  color: var(--c-ink);
  font-size: var(--fs-sm);
  font-weight: 500;
  line-height: 1.3;
  white-space: nowrap;
}
.chip__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
  background: var(--dot, var(--c-text-faint));
  border: 1.5px solid var(--dot, var(--c-text-faint));
}
.chip--verified {
  --dot: var(--c-primary);
}
.chip--tested {
  --dot: var(--c-success);
}
.chip--parsed {
  --dot: #8a8b93;
}
/* "declared": hollow dot */
.chip--declared {
  --dot: #8a8b93;
}
.chip--declared .chip__dot {
  background: transparent;
}
.chip--missing {
  border-style: dashed;
  color: var(--c-text-muted);
  background: transparent;
}
.chip__meter {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 12px;
  margin-left: 2px;
}
.chip__bar {
  width: 3px;
  border-radius: 1px;
  background: var(--c-border-strong);
}
.chip__bar:nth-child(1) {
  height: 5px;
}
.chip__bar:nth-child(2) {
  height: 8px;
}
.chip__bar:nth-child(3) {
  height: 12px;
}
.chip__bar.is-on {
  background: var(--dot, var(--c-primary));
}
</style>
