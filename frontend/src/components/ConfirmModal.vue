<script setup lang="ts">
import AppButton from './AppButton.vue'
import AppModal from './AppModal.vue'

// Confirmation dialog on top of AppModal. It never closes itself on confirm:
// the parent runs the request, then sets v-model to false (so `loading` can show).
withDefaults(
  defineProps<{
    title: string
    /** Plain text under the title; use the default slot for richer content (e.g. a comment field). */
    message?: string
    confirmLabel?: string
    cancelLabel?: string
    /** Red confirm button for destructive actions. */
    danger?: boolean
    loading?: boolean
    /** Disables the confirm button (e.g. while a required field is empty). */
    confirmDisabled?: boolean
  }>(),
  { confirmLabel: 'Подтвердить', cancelLabel: 'Отмена', danger: false, loading: false, confirmDisabled: false },
)

const open = defineModel<boolean>({ default: false })
const emit = defineEmits<{ confirm: [] }>()
</script>

<template>
  <AppModal v-model="open" :title="title" size="sm" :closable="!loading">
    <div class="confirm">
      <p v-if="message" class="confirm__message">{{ message }}</p>
      <slot />
    </div>
    <template #footer>
      <AppButton variant="ghost" :disabled="loading" @click="open = false">{{ cancelLabel }}</AppButton>
      <AppButton
        :variant="danger ? 'danger' : 'primary'"
        :loading="loading"
        :disabled="confirmDisabled"
        @click="emit('confirm')"
      >
        {{ confirmLabel }}
      </AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.confirm {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.confirm__message {
  color: var(--c-text-muted);
  line-height: 1.55;
}
</style>
