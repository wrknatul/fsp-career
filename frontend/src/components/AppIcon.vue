<script setup lang="ts">
import { ICON_PATHS, type IconName } from './icons'

withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 18 })
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path :d="ICON_PATHS[name]" />
  </svg>
</template>

<style scoped>
.icon {
  flex: none;
  display: inline-block;
}
</style>
