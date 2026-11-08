<script setup lang="ts">
import { computed } from 'vue'
import AppBanner from '@/components/ui/AppBanner.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import type { LoadFailure } from '@/composables/useApi'
import { sourceProblems } from '@/lib/sources'
import { exactTime, relativeWords, shortWhen } from '@/lib/time'
import type { Sources } from '@/lib/types'

/**
 * The PageStatus card: how fresh the page is and what it could not read. Three parts, in one
 * polite live region under the page's answer line:
 * - a Banner when the last load failed (with the time of what is still shown, if anything);
 * - the freshness line from `generated_at`;
 * - an error InlineMessage naming every failed read in `sources`, so an empty card never looks
 *   like "none".
 * `failure` may override the Banner's words for a page with its own (the task page's 503).
 */
const props = defineProps<{
  generatedAt: string | null
  checkedAt: Date
  error: LoadFailure | null
  sources: Sources | null
  failure?: { lead: string; text: string } | null
}>()

const banner = computed(() => {
  if (props.failure) return { tone: 'neutral' as const, ...props.failure }
  if (!props.error) return null
  if (props.error.status === 401 || props.error.status === 403)
    return {
      tone: 'error' as const,
      lead: `The console refused this browser (HTTP ${props.error.status}).`,
      text: 'Your Cloudflare Access sign-in may have ended: reload the page to sign in again.',
    }
  let shown = ''
  if (props.generatedAt) {
    const when = shortWhen(props.generatedAt, props.checkedAt)
    shown = `, so this page shows what it had ${/^\d/.test(when) ? `at ${when}` : when}`
  }
  return {
    tone: 'neutral' as const,
    lead: `Couldn’t reach the console’s API${shown}.`,
    text: 'It retries every 30 seconds.',
  }
})

const problems = computed(() => (props.sources ? sourceProblems(props.sources) : []))
const fresh = computed(() =>
  props.generatedAt ? relativeWords(props.generatedAt, props.checkedAt) : '',
)
</script>

<template>
  <div id="page-status" class="grid gap-3" aria-live="polite">
    <AppBanner v-if="banner" id="page-banner" :tone="banner.tone" :lead="banner.lead">
      {{ banner.text }}
    </AppBanner>
    <p v-if="generatedAt" id="page-freshness" class="caption text-ink-secondary">
      Updated {{ fresh }}, at
      <time :datetime="generatedAt" :title="exactTime(generatedAt)">{{
        shortWhen(generatedAt, checkedAt)
      }}</time
      >. Refreshes every 30 seconds.
    </p>
    <InlineMessage v-if="problems.length" id="page-sources" tone="error">
      <p>Some reads failed, so parts of this page are empty.</p>
      <ul class="mt-1 list-disc pl-5">
        <li v-for="p in problems" :key="p.what + p.code">
          Couldn’t read {{ p.what }}: {{ p.why }}. <code class="font-mono">{{ p.code }}</code>
        </li>
      </ul>
    </InlineMessage>
  </div>
</template>
