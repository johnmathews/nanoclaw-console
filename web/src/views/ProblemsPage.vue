<script setup lang="ts">
import { computed, ref } from 'vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import StatusMark from '@/components/ui/StatusMark.vue'
import PageStatus from '@/components/PageStatus.vue'
import TimeText from '@/components/TimeText.vue'
import WarningList from '@/components/WarningList.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { problemsAnswer } from '@/lib/problems'
import { numberWords } from '@/lib/time'
import type { ProblemsView } from '@/lib/types'

/**
 * Errors and warnings (question 5): every problem the API found, in its order (WarningList),
 * then NanoClaw's own host log lines from Loki grouped by message (LogGroupList card): level,
 * message, how often, first and last seen, and the newest line as a sample.
 */
usePageTitle(() => 'Problems')
const { data, error, checkedAt } = useApi<ProblemsView>(ref('/api/problems'))

const answer = computed(() => (data.value ? problemsAnswer(data.value.items) : null))

const logs = computed(() => data.value?.host_logs ?? null)
const logSummary = computed(() => {
  const l = logs.value
  if (!l) return ''
  const window = `in the last ${l.window_hours} hours`
  if (!l.errors && !l.warnings) return `No errors or warnings ${window}.`
  const counts = [
    `${l.errors} ${l.errors === 1 ? 'error' : 'errors'}`,
    `${l.warnings} ${l.warnings === 1 ? 'warning' : 'warnings'}`,
  ].join(' and ')
  const n = l.groups.length
  return `${counts} ${window}, in ${numberWords(n)} ${n === 1 ? 'group' : 'groups'} by message.`
})

function isError(level: string): boolean {
  return level === 'ERROR' || level === 'FATAL'
}
</script>

<template>
  <div id="problems-page" class="grid gap-10">
    <header class="grid gap-3">
      <h1 class="display">Problems</h1>
      <p v-if="answer" id="problems-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="data">
      <section id="problems" aria-labelledby="problems-title" class="grid gap-3">
        <h2 id="problems-title" class="title-1">Needs a look</h2>
        <WarningList
          v-if="data.items.length"
          :items="data.items"
          :now="checkedAt"
          id-prefix="problem"
        />
        <p v-else class="body text-ink-secondary">Nothing needs a look.</p>
      </section>

      <section id="host-logs" aria-labelledby="host-logs-title" class="grid gap-3">
        <h2 id="host-logs-title" class="title-1">NanoClaw’s host logs</h2>
        <template v-if="logs">
          <p id="host-logs-summary" class="body">{{ logSummary }}</p>
          <InlineMessage v-if="logs.truncated" id="host-logs-truncated" tone="caution">
            More lines matched than the console reads (2000); these groups are from the newest.
          </InlineMessage>
          <ul
            v-if="logs.groups.length"
            id="host-log-groups"
            class="divide-y divide-line border-y border-line"
          >
            <li
              v-for="(g, i) in logs.groups"
              :id="`log-group-${i}`"
              :key="`${g.level} ${g.message}`"
              :data-level="g.level"
              class="grid gap-1 py-3 sm:grid-cols-[7rem_1fr] sm:gap-x-4"
            >
              <span class="body"
                ><StatusMark
                  :status="isError(g.level) ? 'failing' : 'degraded'"
                  :label="isError(g.level) ? 'Error' : 'Warning'"
              /></span>
              <div class="grid min-w-0 gap-1">
                <p class="body font-semibold break-words">{{ g.message }}</p>
                <p class="caption flex flex-wrap gap-x-4 text-ink-secondary">
                  <span :id="`log-group-${i}-count`"
                    >{{ g.count }} {{ g.count === 1 ? 'time' : 'times' }}</span
                  >
                  <span :id="`log-group-${i}-seen`"
                    >First <TimeText :at="g.first_at" :now="checkedAt" />, last
                    <TimeText :at="g.last_at" :now="checkedAt" relative
                  /></span>
                </p>
                <pre
                  :id="`log-group-${i}-sample`"
                  class="caption mt-1 font-mono break-all whitespace-pre-wrap text-ink-secondary"
                  >{{ g.sample }}</pre>
              </div>
            </li>
          </ul>
        </template>
        <InlineMessage v-else id="host-logs-unread" tone="error">
          Couldn’t read NanoClaw’s host logs from Loki, so they are not shown.
        </InlineMessage>
      </section>
    </template>
  </div>
</template>
