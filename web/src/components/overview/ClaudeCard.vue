<script setup lang="ts">
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import AppPanel from '@/components/ui/AppPanel.vue'
import StatusMark from '@/components/ui/StatusMark.vue'
import TimeText from '@/components/TimeText.vue'
import { claudeSentence } from '@/lib/overview'
import type { ClaudeHealth } from '@/lib/types'

/**
 * Is Claude working (question 1)? From OneCLI's traffic in Loki and the broker's probe (D6,
 * architecture.md §4.4), never from the quota.
 */
defineProps<{ claude: ClaudeHealth; now: Date }>()

function failures(c: ClaudeHealth): string {
  if (c.auth_failures_1h === null || c.auth_failures_24h === null) return 'Couldn’t read Loki'
  const n = (x: number) => (x === 0 ? 'none' : String(x))
  const sentence = `${n(c.auth_failures_1h)} in the last hour, ${n(c.auth_failures_24h)} in 24 hours`
  return sentence.charAt(0).toUpperCase() + sentence.slice(1)
}
</script>

<template>
  <AppPanel id="claude-card" title="Claude">
    <p class="body">
      <StatusMark id="claude-status" :status="claude.status" />
      <span class="text-ink-secondary"> · </span>{{ claudeSentence(claude.status) }}
    </p>
    <ul
      v-if="claude.reasons.length"
      id="claude-reasons"
      class="caption list-disc pl-5 text-ink-secondary"
    >
      <li v-for="reason in claude.reasons" :key="reason">{{ reason }}</li>
    </ul>
    <FactList>
      <FactItem label="Last success" value-id="claude-last-success">
        <TimeText v-if="claude.last_success_at" :at="claude.last_success_at" :now="now" relative />
        <template v-else>None in the last 24 hours</template>
      </FactItem>
      <FactItem label="Last agent call" value-id="claude-last-call">
        <template v-if="claude.last_agent_call?.at">
          <TimeText :at="claude.last_agent_call.at" :now="now" />, HTTP
          {{ claude.last_agent_call.status ?? 'unknown'
          }}<template v-if="claude.last_agent_call.agent"
            >, from {{ claude.last_agent_call.agent }}</template
          ><template v-if="claude.last_agent_call.injections_applied === 0">
            (OneCLI did not inject the token)</template
          >
        </template>
        <template v-else>None in the last 24 hours</template>
      </FactItem>
      <FactItem label="Agent calls, 24 hours" value-id="claude-agent-calls">
        {{ claude.agent_calls_24h ?? 'Couldn’t read Loki' }}
      </FactItem>
      <FactItem label="Refused tokens" value-id="claude-auth-failures">{{
        failures(claude)
      }}</FactItem>
      <FactItem label="Probe" value-id="claude-probe">
        <template v-if="claude.probe">
          <StatusMark :status="claude.probe.status" class="font-normal" /><template
            v-if="claude.probe.checked_at"
            >, checked <TimeText :at="claude.probe.checked_at" :now="now" /></template
          ><template v-if="claude.probe.http_status !== null">
            (HTTP {{ claude.probe.http_status }})</template
          >
        </template>
        <template v-else>No result from the probe</template>
      </FactItem>
    </FactList>
    <p class="caption text-ink-secondary">
      From OneCLI’s calls to Anthropic and the broker’s probe, not from the quota.
    </p>
  </AppPanel>
</template>
