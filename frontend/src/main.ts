// Combined per-weight files carry a unicode-range for every subset, so the browser downloads only the subsets a
// page really uses. Latin-ext is needed for the ruble sign (U+20BD); the single-subset files have no unicode-range.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
import '@fontsource/jetbrains-mono/700.css'

import './styles/tokens.css'
import './styles/base.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import { setUnauthorizedHandler } from '@/api/client'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useInboxStore } from '@/stores/inbox'
import { useToastStore } from '@/stores/toast'

import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

// Pinia first: the router guard reads stores during the very first navigation.
app.use(pinia)
app.use(router)

// 401 on a protected request while logged in: drop the session and ask to log in again.
setUnauthorizedHandler(() => {
  const auth = useAuthStore(pinia)
  if (!auth.isAuthenticated) {
    // Not logged in (or the session is still being restored): the router guard handles it.
    return
  }
  auth.logout()
  useInboxStore(pinia).reset()
  useToastStore(pinia).info('Сессия истекла. Войдите снова.')
  void router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})

app.mount('#app')
