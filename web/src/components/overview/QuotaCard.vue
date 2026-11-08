<script setup lang="ts">
import AppPanel from '@/components/ui/AppPanel.vue'
import TimeText from '@/components/TimeText.vue'
import type { Quota } from '@/lib/types'

/**
 * The weekly quota, labelled exactly as the API labels it: the host ~/.claude login's, never
 * NanoClaw's token (D6, F7). It plays no part in Claude's status.
 */
defineProps<{ quota: Quota; now: Date }>()
</script>

<template>
  <AppPanel id="quota-card" title="Weekly quota">
    <p id="quota-label" class="caption text-ink-secondary">{{ quota.label }}</p>
    <template v-if="quota.available">
      <template v-if="quota.weekly_pct !== null">
        <p id="quota-used" class="title-2">{{ quota.weekly_pct }}% used</p>
        <div aria-hidden="true" class="h-2 overflow-hidden rounded-full bg-tile">
          <div
            class="h-full rounded-full bg-ink"
            :style="{ width: `${Math.min(100, Math.max(0, quota.weekly_pct))}%` }"
          />
        </div>
      </template>
      <p v-else id="quota-used" class="body">
        The quota text didn’t parse, so the share used is not known.
      </p>
      <p id="quota-resets" class="caption">
        <template v-if="quota.resets_at"
          >Resets <TimeText :at="quota.resets_at" :now="now" relative
        /></template>
        <template v-else-if="quota.resets_text">Resets {{ quota.resets_text }}</template>
        <template v-else>Reset time not known</template>
      </p>
    </template>
    <p v-else class="body">Couldn’t read the quota. It is tried again with the page.</p>
  </AppPanel>
</template>
