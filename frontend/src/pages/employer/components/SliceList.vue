<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'

// A slice of the candidate base (by team role, by work format, by FSP discipline) as a list of bars.
//   mode "link":   a row opens the search (`to`)
//   mode "filter": a row switches the matrix filter (event `select`), the arrow at the end opens the search
// `count: null` = unknown under the current filter (the same dimension is already filtered): the row stays
// clickable, but shows no number and no bar, so that it does not claim "0 candidates".
//   <SliceList title="По роли" :items="roles" mode="filter" :active-key="role" @select="toggleRole" />
export type SliceItem = { key: string; label: string; count: number | null; to: RouteLocationRaw }

const props = withDefaults(
  defineProps<{
    title: string
    hint?: string
    items: readonly SliceItem[]
    mode: 'link' | 'filter'
    activeKey?: string | null
  }>(),
  { hint: '', activeKey: null },
)

const emit = defineEmits<{ select: [key: string] }>()

const maxCount = computed(() => Math.max(1, ...props.items.map((item) => item.count ?? 0)))

function barWidth(count: number | null): string {
  if (count === null || count <= 0) {
    return '0%'
  }
  return `${Math.max(4, (count / maxCount.value) * 100)}%`
}
</script>

<template>
  <section class="slice card" :aria-label="title">
    <header class="slice__head">
      <h3 class="slice__title">{{ title }}</h3>
      <p v-if="hint" class="slice__hint">{{ hint }}</p>
    </header>

    <ul class="slice__list">
      <li v-for="item in items" :key="item.key" class="slice__item" :class="{ 'is-active': activeKey === item.key }">
        <RouterLink v-if="mode === 'link'" class="slice__main" :to="item.to" :class="{ 'is-zero': item.count === 0 }">
          <span class="slice__label">{{ item.label }}</span>
          <span class="slice__count num">{{ item.count ?? '' }}</span>
          <span class="slice__bar" aria-hidden="true"><span class="slice__fill" :style="{ width: barWidth(item.count) }"></span></span>
        </RouterLink>

        <template v-else>
          <button
            type="button"
            class="slice__main"
            :class="{ 'is-zero': item.count === 0 }"
            :aria-pressed="activeKey === item.key"
            @click="emit('select', item.key)"
          >
            <span class="slice__label">{{ item.label }}</span>
            <span class="slice__count num">{{ item.count ?? '' }}</span>
            <span class="slice__bar" aria-hidden="true"><span class="slice__fill" :style="{ width: barWidth(item.count) }"></span></span>
          </button>
          <RouterLink class="slice__go" :to="item.to" :aria-label="`Найти в поиске: ${item.label}`" title="Найти в поиске">
            <AppIcon name="arrow-right" :size="16" />
          </RouterLink>
        </template>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.slice {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
}
.slice__head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.slice__title {
  font-size: var(--fs-base);
}
.slice__hint {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.4;
}
.slice__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  list-style: none;
}
.slice__item {
  display: flex;
  align-items: stretch;
  gap: 2px;
  border-radius: var(--r-md);
}
.slice__item.is-active {
  background: var(--c-primary-soft);
  box-shadow: inset 0 0 0 1px var(--c-primary);
}
.slice__main {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'label count'
    'bar bar';
  align-items: baseline;
  gap: 5px var(--sp-3);
  min-width: 0;
  padding: 8px 10px;
  border: 0;
  border-radius: var(--r-md);
  background: transparent;
  color: var(--c-text);
  font-size: var(--fs-sm);
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}
.slice__main:hover {
  background: var(--c-primary-soft);
  color: var(--c-text);
}
.slice__main.is-zero {
  color: var(--c-text-muted);
}
.slice__label {
  grid-area: label;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.slice__item.is-active .slice__label {
  font-weight: 600;
  color: var(--c-ink);
}
.slice__count {
  grid-area: count;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-ink);
}
.slice__bar {
  grid-area: bar;
  height: 5px;
  border-radius: var(--r-pill);
  background: var(--c-border);
  overflow: hidden;
}
.slice__fill {
  display: block;
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  transition: width 400ms var(--ease);
}
.slice__go {
  display: grid;
  flex: none;
  place-items: center;
  width: 40px;
  border-radius: var(--r-md);
  color: var(--c-text-muted);
}
.slice__go:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
</style>
