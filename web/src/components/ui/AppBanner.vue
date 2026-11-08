<script setup lang="ts">
import { CircleAlert, CloudOff } from '@lucide/vue'

/**
 * The Banner card: a full-width bar under the header saying how the page stands with the API.
 * Neutral when the API cannot be reached (the page keeps retrying), error when it refused.
 * The console's banners carry no button: every page retries by itself every 30 seconds.
 */
defineProps<{ tone: 'neutral' | 'error'; lead: string }>()
</script>

<template>
  <div
    class="flex items-start gap-3 rounded-md border px-4 py-3"
    :class="tone === 'error' ? 'border-error-ink bg-panel' : 'border-line bg-tile'"
  >
    <component
      :is="tone === 'error' ? CircleAlert : CloudOff"
      aria-hidden="true"
      :size="20"
      :stroke-width="1.5"
      class="mt-0.75 flex-none"
      :class="tone === 'error' ? 'text-error-ink' : 'text-ink'"
    />
    <p class="body min-w-0">
      <span class="font-semibold" :class="tone === 'error' ? 'text-error-ink' : ''">{{
        lead
      }}</span>
      {{ ' ' }}<slot />
    </p>
  </div>
</template>
