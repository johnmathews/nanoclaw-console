<script setup lang="ts">
import { computed } from 'vue'
import { Check, CircleAlert, Info, TriangleAlert } from '@lucide/vue'

/** The InlineMessage card: an icon and words in one of four tones, no box and no fill. */
const props = defineProps<{ tone: 'error' | 'caution' | 'success' | 'info' }>()

const look = computed(
  () =>
    ({
      error: { icon: CircleAlert, colour: 'text-error-ink', role: 'alert' },
      caution: { icon: TriangleAlert, colour: 'text-caution-ink', role: 'status' },
      success: { icon: Check, colour: 'text-ink', role: 'status' },
      info: { icon: Info, colour: 'text-ink-secondary', role: 'status' },
    })[props.tone],
)
</script>

<template>
  <div class="caption flex items-start gap-2" :class="look.colour" :role="look.role">
    <component
      :is="look.icon"
      aria-hidden="true"
      :size="16"
      :stroke-width="1.5"
      class="mt-0.75 flex-none"
    />
    <div class="min-w-0"><slot /></div>
  </div>
</template>
