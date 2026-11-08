<script setup lang="ts">
import { computed } from 'vue'
import { exactTime, formatWhen, relativeWords } from '@/lib/time'

/**
 * A time as John reads it, in Amsterdam with the zone named: "today at 15:28 CET". `relative`
 * adds "(two minutes ago)" inline, or on its own line with `stacked`. The exact time is in the
 * element's datetime and its tooltip.
 */
const props = defineProps<{ at: string; now: Date; relative?: boolean; stacked?: boolean }>()
const when = computed(() => formatWhen(props.at, props.now))
const ago = computed(() => relativeWords(props.at, props.now))
</script>

<template>
  <time :datetime="at" :title="exactTime(at)">
    {{ when
    }}<template v-if="relative && ago"
      ><template v-if="stacked"
        >{{ ' ' }}<span class="caption block text-ink-secondary">{{ ago }}</span></template
      ><template v-else> ({{ ago }})</template></template
    >
  </time>
</template>
