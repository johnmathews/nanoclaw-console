<script setup lang="ts">
import { computed } from 'vue'

/**
 * The StatusMark card (brand/design-system/project/components/StatusMark): a 10px dot in the
 * status's pen, then the words. The words always carry the meaning (B2); the dot only repeats it.
 * `unknown` is a hollow ring, since it is not one of the three pens.
 */
const props = defineProps<{
  status: 'ok' | 'degraded' | 'failing' | 'unknown'
  /** The words; defaults to the status's own name. */
  label?: string
}>()

const WORDS = { ok: 'OK', degraded: 'Degraded', failing: 'Failing', unknown: 'Unknown' }
const words = computed(() => props.label ?? WORDS[props.status])
const dot = computed(
  () =>
    ({
      ok: 'bg-pen',
      degraded: 'bg-pen-partial',
      failing: 'bg-pen-missed',
      unknown: 'border-2 border-control-border',
    })[props.status],
)
</script>

<template>
  <span class="inline-flex items-center gap-2 font-semibold" :data-status="status">
    <span aria-hidden="true" class="size-2.5 flex-none rounded-full" :class="dot" />
    <span>{{ words }}</span>
  </span>
</template>
