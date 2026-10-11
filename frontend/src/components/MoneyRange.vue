<script setup lang="ts">
import { computed } from 'vue'

import { formatMoney, formatMoneyRange } from '@/utils/format'

// Money in the mono font.
//   <MoneyRange :amount="offer.salary" size="lg" />                       one sum: "120 000 ₽"
//   <MoneyRange :from="v.salary_from" :to="v.salary_to" />                range: "120 000 – 200 000 ₽", "от …", "до …"
const props = withDefaults(
  defineProps<{
    from?: number | null
    to?: number | null
    /** A single sum (takes precedence over from/to). */
    amount?: number | null
    size?: 'sm' | 'md' | 'lg' | 'xl'
    /** Text when nothing is set. */
    emptyText?: string
  }>(),
  { from: null, to: null, amount: null, size: 'md', emptyText: 'Не указана' },
)

const text = computed(() => {
  if (props.amount !== null) {
    return formatMoney(props.amount)
  }
  return formatMoneyRange(props.from, props.to, props.emptyText)
})
const isEmpty = computed(() => props.amount === null && props.from === null && props.to === null)
</script>

<template>
  <span class="money num" :class="[`money--${size}`, { 'money--empty': isEmpty }]">{{ text }}</span>
</template>

<style scoped>
.money {
  font-weight: 600;
  color: var(--c-ink);
  white-space: nowrap;
}
.money--sm {
  font-size: var(--fs-sm);
}
.money--md {
  font-size: var(--fs-base);
}
.money--lg {
  font-size: var(--fs-xl);
  letter-spacing: -0.03em;
}
.money--xl {
  font-size: clamp(1.75rem, 1.3rem + 1.8vw, 2.5rem);
  letter-spacing: -0.04em;
}
.money--empty {
  font-family: var(--font-sans);
  font-weight: 400;
  color: var(--c-text-muted);
}
</style>
