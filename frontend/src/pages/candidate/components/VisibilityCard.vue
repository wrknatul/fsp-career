<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import { patchProfile } from '@/api/candidate'
import type { CandidateProfile } from '@/api/types'
import AppIcon from '@/components/AppIcon.vue'
import { useToastStore } from '@/stores/toast'

import { previewDisplayName } from './helpers'

// "Показывать профиль работодателям": the switch and a plain list of what an employer sees before an offer.
const props = defineProps<{ profile: CandidateProfile }>()
const emit = defineEmits<{ updated: [profile: CandidateProfile] }>()

const toast = useToastStore()
const titleId = useId()
const busy = ref(false)

const visible = computed(() => props.profile.visible)
const asSeen = computed(() => previewDisplayName(props.profile.user.full_name))
const hiddenByCategory = computed(() => visible.value && props.profile.category.stack === null)

async function toggle(): Promise<void> {
  if (busy.value) {
    return
  }
  busy.value = true
  try {
    const next = await patchProfile({ visible: !props.profile.visible })
    emit('updated', next)
    toast.success(next.visible ? 'Профиль виден работодателям' : 'Профиль скрыт от работодателей')
  } catch (err) {
    toast.fromError(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="vis card" :aria-labelledby="titleId">
    <header class="vis__head">
      <div class="vis__text">
        <h3 :id="titleId" class="vis__title">Показывать профиль работодателям</h3>
        <p class="vis__state" :class="{ 'is-on': visible }">
          {{
            visible
              ? 'Включено: работодатели находят вас в поиске по категории.'
              : 'Выключено: работодатели вас не найдут, офферы не придут.'
          }}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        class="switch"
        :class="{ 'is-on': visible }"
        :aria-checked="visible"
        :aria-labelledby="titleId"
        :disabled="busy"
        @click="toggle"
      >
        <span class="switch__thumb"></span>
      </button>
    </header>

    <p v-if="hiddenByCategory" class="callout callout--warning">
      <AppIcon name="alert" :size="16" />
      <span>Пока категория не определена, в поиске вас не будет. Привяжите ФСП, добавьте резюме или сдайте тест.</span>
    </p>

    <div class="vis__lists">
      <div class="vis__col">
        <p class="vis__col-title">До оффера работодатель видит</p>
        <ul class="vis__list">
          <li>
            <AppIcon name="check" :size="14" />
            <span>
              Имя и первую букву фамилии<template v-if="asSeen">: <b class="mono nowrap">{{ asSeen }}</b></template>
            </span>
          </li>
          <li><AppIcon name="check" :size="14" /><span>Город, категорию, грейд и роль</span></li>
          <li><AppIcon name="check" :size="14" /><span>Навыки, результаты ФСП и разряд с отметкой источника</span></li>
          <li><AppIcon name="check" :size="14" /><span>Зарплатные ожидания и «о себе» без контактов</span></li>
        </ul>
      </div>
      <div class="vis__col">
        <p class="vis__col-title">Скрыто, пока вы не примете оффер</p>
        <ul class="vis__list vis__list--hidden">
          <li><AppIcon name="lock" :size="14" /><span>Полное ФИО и дата рождения</span></li>
          <li><AppIcon name="lock" :size="14" /><span>Почта, телефон и Telegram</span></li>
          <li><AppIcon name="lock" :size="14" /><span>Текст резюме</span></li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.vis {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.vis__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
}
.vis__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.vis__title {
  font-size: var(--fs-base);
  line-height: 1.35;
}
.vis__state {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
}
.vis__state.is-on {
  color: var(--c-success-text);
}
.switch {
  position: relative;
  flex: none;
  width: 52px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: var(--r-pill);
  background: #b3b3bc;
  transition: background var(--t-base) var(--ease);
}
.switch.is-on {
  background: var(--c-success);
}
.switch:disabled {
  opacity: 0.6;
  cursor: progress;
}
.switch__thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(27, 28, 33, 0.3);
  transition: transform var(--t-base) var(--ease);
}
.switch.is-on .switch__thumb {
  transform: translateX(22px);
}
.vis__lists {
  display: grid;
  gap: var(--sp-4);
  grid-template-columns: 1fr;
}
.vis__col {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
}
.vis__col-title {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.vis__list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--fs-sm);
  line-height: 1.45;
}
.vis__list li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.vis__list li :deep(svg) {
  margin-top: 3px;
  color: var(--c-success-text);
}
.vis__list--hidden li {
  color: var(--c-text-muted);
}
.vis__list--hidden li :deep(svg) {
  color: var(--c-text-muted);
}

@media (min-width: 560px) {
  .vis__lists {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--sp-6);
  }
}
</style>
