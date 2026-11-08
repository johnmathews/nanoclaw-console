<script setup lang="ts">
import StatusMark from '@/components/ui/StatusMark.vue'
import TimeText from '@/components/TimeText.vue'
import type { ProblemItem } from '@/lib/types'

/**
 * The WarningList card: problem items (§4.7), worst first as the API sorts them. Each has its
 * severity as a StatusMark with the word (Error, Warning, Note), the title, the detail, when, and
 * a link to the task it is about. W9's Problems page reuses it.
 */
defineProps<{ items: ProblemItem[]; now: Date; idPrefix: string }>()

const MARK = { error: 'failing', warning: 'degraded', info: 'unknown' } as const
const WORD = { error: 'Error', warning: 'Warning', info: 'Note' } as const
</script>

<template>
  <ul class="divide-y divide-line border-y border-line">
    <li
      v-for="(item, i) in items"
      :id="`${idPrefix}-${item.kind}-${i}`"
      :key="`${item.kind}-${i}`"
      class="grid gap-1 py-3 sm:grid-cols-[7rem_1fr] sm:gap-x-4"
    >
      <span class="body"
        ><StatusMark :status="MARK[item.severity]" :label="WORD[item.severity]"
      /></span>
      <div class="min-w-0">
        <p class="body font-semibold">{{ item.title }}</p>
        <p v-if="item.detail" class="caption text-ink-secondary">{{ item.detail }}</p>
        <p class="caption mt-1 flex flex-wrap gap-x-4 text-ink-secondary">
          <TimeText v-if="item.at" :at="item.at" :now="now" relative />
          <RouterLink
            v-if="item.ref?.type === 'task'"
            :to="`/tasks/${item.ref.id}`"
            class="text-ink underline underline-offset-[3px] hover:decoration-2"
          >
            Open the task
          </RouterLink>
        </p>
      </div>
    </li>
  </ul>
</template>
