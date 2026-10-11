<script setup lang="ts">
import type { OfferStatus } from '@/api/types'
import { OFFER_STATUS_TITLES } from '@/utils/labels'

// Status of an offer as a pill: the word carries the meaning, the colour only supports it.
//   <OfferStatusBadge status="sent" />   -> "Ждёт ответа"
withDefaults(defineProps<{ status: OfferStatus; prefix?: string }>(), { prefix: '' })
</script>

<template>
  <span class="status" :class="`status--${status}`">
    <span class="status__dot" aria-hidden="true"></span>
    <span v-if="prefix" class="status__prefix">{{ prefix }}</span>
    {{ OFFER_STATUS_TITLES[status] }}
  </span>
</template>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
  font-size: var(--fs-xs);
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
}
.status__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
.status__prefix {
  font-weight: 500;
  opacity: 0.8;
}
.status--sent {
  background: var(--c-warning-soft);
  border-color: var(--c-warning-border);
  color: var(--c-warning-text);
}
.status--accepted {
  background: var(--c-success-soft);
  border-color: var(--c-success-border);
  color: var(--c-success-text);
}
.status--declined {
  background: var(--c-danger-soft);
  border-color: var(--c-danger-border);
  color: var(--c-danger-text);
}
</style>
