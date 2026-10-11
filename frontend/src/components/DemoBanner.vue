<script setup lang="ts">
import { useReferenceStore } from '@/stores/reference'

// Thin strip above the header while the FSP registry is simulated (fsp_registry_mode = 'mock').
const reference = useReferenceStore()
</script>

<template>
  <div v-if="reference.isMock" class="demo-banner" role="note">
    <span class="demo-banner__dot" aria-hidden="true"></span>
    Демо-стенд: данные реестра ФСП смоделированы
  </div>
</template>

<style scoped>
.demo-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px var(--gutter);
  background: var(--c-ink);
  color: var(--c-on-ink);
  font-size: var(--fs-xs);
  font-weight: 500;
  line-height: 1.4;
  text-align: center;
}
.demo-banner__dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8f86ff;
}
</style>
