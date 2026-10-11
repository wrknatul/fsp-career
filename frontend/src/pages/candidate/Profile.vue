<script setup lang="ts">
import { nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getProfile } from '@/api/candidate'
import FactList from '@/components/FactList.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'

import AchievementsBlock from './components/AchievementsBlock.vue'
import QuestionnaireForm from './components/QuestionnaireForm.vue'
import ResumeBlock from './components/ResumeBlock.vue'

// Three blocks that fill the profile by hand: questionnaire, resume, achievements. All facts are listed below.
const { data: profile, status, errorMessage, load, setData } = useLoader(() => getProfile())

// The router scrolls to a #hash once, before the blocks exist (they render after the profile loads).
// Repeat the jump when the first load finishes; section scroll-margin keeps the offset under the header.
const route = useRoute()
let anchorHandled = false
watch(status, async (value) => {
  if (value !== 'ready' || anchorHandled) {
    return
  }
  anchorHandled = true
  if (route.hash === '') {
    return
  }
  await nextTick()
  let target: Element | null = null
  try {
    target = document.querySelector(route.hash)
  } catch {
    target = null // not a valid selector: nothing to scroll to
  }
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
})
</script>

<template>
  <PageHeader
    title="Анкета и факты профиля"
    eyebrow="Соискатель"
    subtitle="Здесь вы сами заполняете то, чего нет в реестре ФСП. У каждого факта ниже есть источник и степень подтверждения."
  />

  <StateBlock v-if="status === 'loading'" state="loading" title="Загружаем анкету…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />

  <template v-else-if="profile">
    <div class="pf">
      <div class="pf__col">
        <QuestionnaireForm :profile="profile" @saved="setData" />
      </div>
      <div class="pf__col">
        <ResumeBlock :profile="profile" @updated="setData" />
        <AchievementsBlock :profile="profile" @updated="setData" />
      </div>
    </div>

    <section class="stack" aria-labelledby="facts-title">
      <h2 id="facts-title" class="section-title">Все факты профиля</h2>
      <div class="card">
        <FactList :facts="profile.facts" />
      </div>
    </section>
  </template>
</template>

<style scoped>
.pf {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-6);
  align-items: start;
}
.pf__col {
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
  min-width: 0;
}

@media (min-width: 1000px) {
  .pf {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
</style>
