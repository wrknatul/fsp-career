<script setup lang="ts">
import { computed } from 'vue'

// Question and option text from the bank: `inline code` and ```fenced blocks``` become code, the rest stays text.
// Rendered through plain nodes (no v-html), so nothing from the bank can inject markup.
const props = withDefaults(defineProps<{ text: string; inline?: boolean }>(), { inline: false })

type Token = { kind: 'text' | 'code' | 'block'; value: string }

const FENCE = /```[a-zA-Z0-9_+-]*\n?([\s\S]*?)```/g
const INLINE = /`([^`\n]+)`/g

function splitInline(text: string): Token[] {
  const tokens: Token[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0
    if (start > last) {
      tokens.push({ kind: 'text', value: text.slice(last, start) })
    }
    tokens.push({ kind: 'code', value: match[1] })
    last = start + match[0].length
  }
  if (last < text.length) {
    tokens.push({ kind: 'text', value: text.slice(last) })
  }
  return tokens
}

const tokens = computed<Token[]>(() => {
  const result: Token[] = []
  let last = 0
  for (const match of props.text.matchAll(FENCE)) {
    const start = match.index ?? 0
    if (start > last) {
      result.push(...splitInline(props.text.slice(last, start)))
    }
    result.push({ kind: 'block', value: match[1].replace(/^\n+|\s+$/g, '') })
    last = start + match[0].length
  }
  if (last < props.text.length) {
    result.push(...splitInline(props.text.slice(last)))
  }
  return result
})
</script>

<template>
  <component :is="inline ? 'span' : 'div'" class="qt">
    <template v-for="(token, index) in tokens" :key="index">
      <pre v-if="token.kind === 'block'" class="qt__block"><code>{{ token.value }}</code></pre>
      <code v-else-if="token.kind === 'code'" class="qt__code">{{ token.value }}</code>
      <template v-else>{{ token.value }}</template>
    </template>
  </component>
</template>

<style scoped>
.qt {
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.qt__code {
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--c-neutral-soft);
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--c-ink);
  white-space: pre-wrap;
}
.qt__block {
  display: block;
  margin: var(--sp-2) 0;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-ink);
  color: var(--c-on-ink);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  line-height: 1.6;
  white-space: pre;
  overflow-x: auto;
}
.qt__block code {
  font-family: inherit;
}
</style>
