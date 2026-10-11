<script setup lang="ts">
import { computed } from 'vue'

import type { CandidateContacts } from '@/api/types'

// Contacts of a candidate who accepted the offer. Links are built only from values that look
// like an e-mail / a Telegram name / a phone number: the text itself is always shown as plain text.
//   <ContactLines :contacts="card.contacts" />
const props = defineProps<{ contacts: CandidateContacts }>()

const EMAIL_PATTERN = /^[^\s@<>"']+@[^\s@<>"']+\.[^\s@<>"']+$/
const TELEGRAM_PATTERN = /^[A-Za-z0-9_]{3,32}$/
const PHONE_PATTERN = /^\+?\d{6,15}$/

type Line = { key: string; label: string; text: string; href: string | null }

function emailHref(value: string): string | null {
  return EMAIL_PATTERN.test(value) ? `mailto:${value}` : null
}

function telegramHref(value: string): string | null {
  const name = value
    .trim()
    .replace(/^https?:\/\/t\.me\//i, '')
    .replace(/^@/, '')
  return TELEGRAM_PATTERN.test(name) ? `https://t.me/${name}` : null
}

function phoneHref(value: string): string | null {
  const compact = value.replace(/[\s()-]/g, '')
  return PHONE_PATTERN.test(compact) ? `tel:${compact}` : null
}

const lines = computed<Line[]>(() => {
  const result: Line[] = [{ key: 'email', label: 'Почта', text: props.contacts.email, href: emailHref(props.contacts.email) }]
  if (props.contacts.telegram) {
    result.push({
      key: 'telegram',
      label: 'Telegram',
      text: props.contacts.telegram,
      href: telegramHref(props.contacts.telegram),
    })
  }
  if (props.contacts.phone) {
    result.push({ key: 'phone', label: 'Телефон', text: props.contacts.phone, href: phoneHref(props.contacts.phone) })
  }
  return result
})
</script>

<template>
  <dl class="contacts">
    <div v-for="line in lines" :key="line.key" class="contacts__row">
      <dt>{{ line.label }}</dt>
      <dd>
        <a v-if="line.href" class="contacts__value num" :href="line.href" rel="noopener noreferrer">{{ line.text }}</a>
        <span v-else class="contacts__value num">{{ line.text }}</span>
      </dd>
    </div>
  </dl>
</template>

<style scoped>
.contacts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: 0;
}
.contacts__row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px var(--sp-3);
}
.contacts dt {
  min-width: 72px;
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.contacts dd {
  margin: 0;
  min-width: 0;
}
.contacts__value {
  font-size: var(--fs-sm);
  font-weight: 500;
  overflow-wrap: anywhere;
}
</style>
