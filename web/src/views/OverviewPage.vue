<script setup lang="ts">
import { computed, ref } from 'vue'
import ClaudeCard from '@/components/overview/ClaudeCard.vue'
import CountsCard from '@/components/overview/CountsCard.vue'
import NanoclawCard from '@/components/overview/NanoclawCard.vue'
import QuotaCard from '@/components/overview/QuotaCard.vue'
import PageStatus from '@/components/PageStatus.vue'
import WarningList from '@/components/WarningList.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { claudeSentence, nanoclawSentence } from '@/lib/overview'
import type { Overview } from '@/lib/types'

/**
 * The overview: is Claude working, is NanoClaw running, what needs a look. The answer line
 * first, then the warnings, then four cards (two columns from 1024px).
 */
usePageTitle(() => 'Overview')
const { data, error, checkedAt } = useApi<Overview>(ref('/api/overview'))
const answer = computed(() =>
  data.value
    ? `${claudeSentence(data.value.claude.status)} ${nanoclawSentence(data.value.nanoclaw)}`
    : null,
)
</script>

<template>
  <div id="overview-page" class="grid gap-10">
    <header class="grid gap-3">
      <h1 class="display">Overview</h1>
      <p v-if="answer" id="overview-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="data">
      <section id="warnings" aria-labelledby="warnings-title" class="grid gap-3">
        <h2 id="warnings-title" class="title-1">Needs a look</h2>
        <WarningList
          v-if="data.warnings.length"
          :items="data.warnings"
          :now="checkedAt"
          id-prefix="warning"
        />
        <p v-else class="body text-ink-secondary">Nothing needs a look.</p>
      </section>

      <div class="grid items-start gap-6 lg:grid-cols-2">
        <ClaudeCard :claude="data.claude" :now="checkedAt" />
        <NanoclawCard :nanoclaw="data.nanoclaw" :now="checkedAt" />
        <QuotaCard :quota="data.quota" :now="checkedAt" />
        <CountsCard :counts="data.counts" />
      </div>
    </template>
  </div>
</template>
