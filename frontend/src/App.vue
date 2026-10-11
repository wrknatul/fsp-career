<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppToasts from '@/components/AppToasts.vue'
import { useReferenceStore } from '@/stores/reference'

// Dictionaries are needed almost everywhere (titles, the demo banner): start loading right away.
// The call never throws; pages read `reference.status` if they need to react to a failure.
void useReferenceStore().load()
</script>

<template>
  <RouterView />
  <AppToasts />
</template>
