<script setup lang="ts">
import { computed } from 'vue'
import { policyWords, type PolicyAxis } from '@/lib/groups'

/**
 * A wiring or channel policy as words, with NanoClaw's own value beside them in monospace, so it
 * can be matched against `ncl` (RecordList card).
 */
const props = defineProps<{ axis: PolicyAxis; value: string | null }>()
const words = computed(() => policyWords(props.axis, props.value))
</script>

<template>
  <span
    >{{ words
    }}<template v-if="value !== null"
      >{{ ' ' }}<code class="font-mono text-ink-secondary">{{ value }}</code></template
    ></span
  >
</template>
