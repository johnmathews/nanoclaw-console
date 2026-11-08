<script setup lang="ts">
import { computed, ref } from 'vue'
import AuditList from '@/components/AuditList.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import PageStatus from '@/components/PageStatus.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { auditAnswer } from '@/lib/actions'
import type { AuditView } from '@/lib/types'

/**
 * The audit log (release 2, architecture.md §5.8): every pause, resume, run and restart asked of
 * the console, newest first, refusals included, with who asked and what NanoClaw answered. It
 * also says when the log cannot be written, because the four actions are refused until it can.
 */
usePageTitle(() => 'Audit log')
const { data, error, checkedAt } = useApi<AuditView>(ref('/api/audit'))

const answer = computed(() => (data.value ? auditAnswer(data.value.entries, checkedAt.value) : ''))
</script>

<template>
  <div id="audit-page" class="grid gap-10">
    <header class="grid gap-3">
      <h1 class="display">Audit log</h1>
      <p v-if="data" id="audit-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="null"
      />
    </header>

    <template v-if="data">
      <InlineMessage v-if="!data.available" id="audit-unreadable" tone="error">
        <p class="body">
          Couldn’t read the audit log, so nothing can be listed. Pause, resume, run and restart are
          refused while it can’t be written.
        </p>
      </InlineMessage>
      <InlineMessage v-else-if="!data.writable" id="audit-unwritable" tone="error">
        <p class="body">
          The console can’t write its audit log, so pause, resume, run and restart are refused until
          it can.
        </p>
      </InlineMessage>

      <section
        v-if="data.available"
        id="audit"
        aria-labelledby="audit-title"
        class="grid max-w-3xl gap-3"
      >
        <h2 id="audit-title" class="title-1">What was asked</h2>
        <p class="body text-ink-secondary">
          Newest first{{ data.truncated ? ', from the most recent part of the log' : '' }}. Requests
          the console refused are listed too; NanoClaw never saw those.
        </p>
        <AuditList :entries="data.entries" :now="checkedAt" />
      </section>
    </template>
  </div>
</template>
