import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getErrorMessage } from '@/api/client'
import { listOffers } from '@/api/candidate'

/**
 * Candidate inbox counter: number of offers waiting for an answer (status 'sent').
 * Shown as a badge on the "Офферы" tab. Pages that answer or list offers call
 * `refresh()` (or `setPending()` when they already hold the list) to keep it fresh.
 */
export const useInboxStore = defineStore('inbox', () => {
  const pendingOffers = ref(0)
  const lastError = ref('')

  async function refresh(): Promise<void> {
    try {
      const offers = await listOffers()
      pendingOffers.value = offers.filter((offer) => offer.status === 'sent').length
      lastError.value = ''
    } catch (err) {
      // The badge is secondary: keep the previous number and remember why it is stale.
      lastError.value = getErrorMessage(err)
    }
  }

  function setPending(count: number): void {
    pendingOffers.value = Math.max(0, count)
  }

  function reset(): void {
    pendingOffers.value = 0
    lastError.value = ''
  }

  return { pendingOffers, lastError, refresh, setPending, reset }
})
