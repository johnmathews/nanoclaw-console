<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronLeft } from '@lucide/vue'
import AccessMark from '@/components/ui/AccessMark.vue'
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import PageStatus from '@/components/PageStatus.vue'
import PolicyValue from '@/components/PolicyValue.vue'
import TimeText from '@/components/TimeText.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { channelLabel, domId, engageWords, groupName, mcpWhere } from '@/lib/groups'
import type { Destination, GroupsView, McpServer } from '@/lib/types'
import { listWords } from '@/lib/words'

/**
 * One group in full (question 2): its model and settings, each wired channel with its engage,
 * sender and unknown-sender policies, its MCP servers (name and host only), its mounts with
 * read-write flagged, and whom it may message. It reads /api/groups, which answers for every
 * group, and picks this one. The header leaves room at its right for release 2's restart (W15).
 */
const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error, checkedAt } = useApi<GroupsView>(ref('/api/groups'))

const group = computed(() => data.value?.groups.find((g) => g.id === id.value) ?? null)
const listFailed = computed(
  () => !!data.value && !group.value && 'groups-list' in data.value.sources.broker.errors,
)
const missing = computed(() => !!data.value && !group.value)
const title = computed(() =>
  group.value ? groupName(group.value) : missing.value ? 'Group not found' : 'Group',
)
usePageTitle(() => title.value)

const config = computed(() => group.value?.config ?? null)

const SETTINGS = [
  ['effort', 'Effort'],
  ['speed', 'Speed'],
  ['assistant_name', 'Assistant name'],
  ['cli_scope', 'CLI scope'],
  ['timezone', 'Time zone'],
  ['image_tag', 'Image'],
  ['max_messages_per_prompt', 'Messages per prompt'],
  ['skills', 'Skills'],
] as const

const packages = computed(() => {
  const c = config.value
  if (!c) return ''
  const parts = []
  if (c.packages_apt.length) parts.push(`apt: ${c.packages_apt.join(', ')}`)
  if (c.packages_npm.length) parts.push(`npm: ${c.packages_npm.join(', ')}`)
  return parts.length ? parts.join('; ') : 'None'
})

const tasksWords = computed(() => {
  const t = group.value?.tasks
  if (!t?.total) return 'None'
  let s = `${t.total} ${t.total === 1 ? 'task' : 'tasks'}`
  if (t.paused) s += `, ${t.paused} paused`
  return s
})

/** What a server is given that the console does not show: header and env names, arg count. */
function secretsWords(s: McpServer): string | null {
  const parts: string[] = []
  if (s.header_names.length)
    parts.push(
      `Sends ${s.header_names.length === 1 ? 'header' : 'headers'} ${s.header_names.join(', ')}`,
    )
  if (s.env_names.length)
    parts.push(`${parts.length ? 'sets' : 'Sets'} env ${s.env_names.join(', ')}`)
  if (s.arg_count)
    parts.push(
      `${parts.length ? 'passes' : 'Passes'} ${s.arg_count} ${s.arg_count === 1 ? 'argument' : 'arguments'}`,
    )
  if (!parts.length) return null
  const many =
    parts.length > 1 || s.header_names.length > 1 || s.env_names.length > 1 || s.arg_count > 1
  return `${listWords(parts)}; ${many ? 'their values are' : 'its value is'} not shown`
}

function destinationWords(d: Destination): string {
  const target = d.target_name ?? d.target_id ?? 'an unknown target'
  const kind =
    d.target_type === 'agent'
      ? 'an agent'
      : d.target_type === 'channel'
        ? `a ${d.channel_type ?? ''} channel`.replace('  ', ' ')
        : (d.target_type ?? 'unknown kind')
  return `${d.local_name ?? 'unnamed'} → ${target} (${kind})`
}
</script>

<template>
  <div id="group-page" class="grid gap-10">
    <header class="grid gap-3">
      <p class="caption">
        <RouterLink
          id="group-back"
          to="/groups"
          class="inline-flex min-h-11 items-center gap-1 underline underline-offset-[3px] hover:decoration-2"
        >
          <ChevronLeft aria-hidden="true" :size="16" :stroke-width="1.5" />All groups
        </RouterLink>
      </p>
      <div class="flex flex-wrap items-start justify-between gap-4">
        <h1 class="display min-w-0 break-words">{{ title }}</h1>
      </div>
      <p
        v-if="group"
        id="group-ids"
        class="caption flex flex-wrap gap-x-4 font-mono break-all text-ink-secondary"
      >
        <code v-if="group.folder">{{ group.folder }}</code
        >{{ group.folder ? ' ' : '' }}<code>{{ group.id }}</code>
      </p>
      <p v-else-if="listFailed" id="group-missing" class="body-large">
        Couldn’t read the group list, so this group can’t be shown. It retries every 30 seconds.
      </p>
      <p v-else-if="missing" id="group-missing" class="body-large">
        There is no group {{ id }}. It may have been removed.
        <RouterLink to="/groups" class="underline underline-offset-[3px]"
          >See every group</RouterLink
        >.
      </p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="group">
      <InlineMessage v-if="!config" id="group-config-failed" tone="error">
        Couldn’t read this group’s config, so its model, MCP servers and mounts are not shown. It
        retries every 30 seconds.
      </InlineMessage>

      <section id="group-settings" aria-labelledby="group-settings-title" class="grid gap-4">
        <h2 id="group-settings-title" class="title-1">Model and settings</h2>
        <FactList>
          <template v-if="config">
            <FactItem label="Model" value-id="group-model">{{
              config.model ?? 'Not set (NanoClaw’s default)'
            }}</FactItem>
            <FactItem label="Provider" value-id="group-provider">{{
              config.provider ?? 'Not set (NanoClaw’s default)'
            }}</FactItem>
            <FactItem
              v-for="[key, label] in SETTINGS"
              :key="key"
              :label="label"
              :value-id="`group-${key.replace(/_/g, '-')}`"
              >{{ config[key] ?? 'Not set' }}</FactItem
            >
            <FactItem label="Packages" value-id="group-packages">{{ packages }}</FactItem>
            <FactItem label="Config changed" value-id="group-config-updated">
              <TimeText
                v-if="config.updated_at"
                :at="config.updated_at"
                :now="checkedAt"
                relative
              />
              <template v-else>Not known</template>
            </FactItem>
          </template>
          <FactItem label="Tasks" value-id="group-tasks">
            {{ tasksWords }}
            <RouterLink
              v-if="group.tasks.total"
              to="/tasks"
              class="underline underline-offset-[3px] hover:decoration-2"
              >See the tasks</RouterLink
            >
          </FactItem>
          <FactItem label="Sessions" value-id="group-sessions"
            >{{ group.sessions.total }}, {{ group.sessions.running }} running</FactItem
          >
          <FactItem label="Created" value-id="group-created">
            <TimeText v-if="group.created_at" :at="group.created_at" :now="checkedAt" />
            <template v-else>Not known</template>
          </FactItem>
        </FactList>
      </section>

      <section id="group-channels" aria-labelledby="group-channels-title" class="grid gap-3">
        <h2 id="group-channels-title" class="title-1">Channels</h2>
        <ul v-if="group.channels.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="(c, i) in group.channels"
            :id="`group-channel-${domId(c.wiring_id ?? String(i))}`"
            :key="c.wiring_id ?? i"
            class="grid gap-3 py-4"
          >
            <div class="grid gap-1">
              <h3 class="body font-semibold break-words">{{ channelLabel(c) }}</h3>
              <p class="caption text-ink-secondary">
                {{ c.channel_type ?? 'Unknown type'
                }}{{ c.is_group === null ? '' : c.is_group ? ', a group chat' : ', a direct chat' }}
                ·
                <code class="font-mono break-all">{{ c.platform_id ?? 'no platform id' }}</code>
              </p>
            </div>
            <FactList>
              <FactItem
                label="Engages on"
                :value-id="`group-channel-${domId(c.wiring_id ?? String(i))}-engage`"
              >
                {{ engageWords(c) }}
                <template v-if="c.engage_mode === 'pattern' && c.engage_pattern !== null"
                  >(pattern <code class="font-mono break-all">{{ c.engage_pattern }}</code
                  >)</template
                >
                <code v-else-if="c.engage_mode" class="font-mono text-ink-secondary">{{
                  c.engage_mode
                }}</code>
              </FactItem>
              <FactItem
                label="Who may engage it"
                :value-id="`group-channel-${domId(c.wiring_id ?? String(i))}-senders`"
              >
                <PolicyValue axis="sender_scope" :value="c.sender_scope" />
              </FactItem>
              <FactItem
                label="Unknown senders"
                :value-id="`group-channel-${domId(c.wiring_id ?? String(i))}-unknown`"
              >
                <PolicyValue axis="unknown_sender_policy" :value="c.unknown_sender_policy" />
              </FactItem>
              <FactItem
                label="Other messages"
                :value-id="`group-channel-${domId(c.wiring_id ?? String(i))}-ignored`"
              >
                <PolicyValue axis="ignored_message_policy" :value="c.ignored_message_policy" />
              </FactItem>
              <FactItem
                label="Sessions"
                :value-id="`group-channel-${domId(c.wiring_id ?? String(i))}-sessions`"
              >
                <PolicyValue axis="session_mode" :value="c.session_mode" />
              </FactItem>
              <FactItem label="Priority">{{ c.priority ?? 'Not set' }}</FactItem>
            </FactList>
            <InlineMessage v-if="c.denied_at" tone="caution">
              The channel was denied <TimeText :at="c.denied_at" :now="checkedAt" />.
            </InlineMessage>
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">
          No channel is wired to this group, so it only runs scheduled tasks and messages from other
          agents.
        </p>
      </section>

      <section v-if="config" id="group-mcp" aria-labelledby="group-mcp-title" class="grid gap-3">
        <h2 id="group-mcp-title" class="title-1">MCP servers</h2>
        <ul v-if="config.mcp_servers.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="s in config.mcp_servers"
            :id="`mcp-${domId(s.name)}`"
            :key="s.name"
            class="grid gap-2 py-4"
          >
            <h3 class="body font-semibold break-words">
              {{ s.name }}
              <span class="caption font-normal text-ink-secondary">{{
                [s.type, s.transport].filter(Boolean).join(', ') || 'type not known'
              }}</span>
            </h3>
            <FactList>
              <FactItem :label="mcpWhere(s).label" :value-id="`mcp-${domId(s.name)}-where`">
                <code v-if="mcpWhere(s).value" class="font-mono break-all">{{
                  mcpWhere(s).value
                }}</code>
                <template v-else>Not known</template>
              </FactItem>
            </FactList>
            <p
              v-if="secretsWords(s)"
              :id="`mcp-${domId(s.name)}-secrets`"
              class="caption text-ink-secondary"
            >
              {{ secretsWords(s) }}
            </p>
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">No MCP servers.</p>
      </section>

      <section
        v-if="config"
        id="group-mounts"
        aria-labelledby="group-mounts-title"
        class="grid gap-3"
      >
        <h2 id="group-mounts-title" class="title-1">Mounts</h2>
        <ul v-if="config.mounts.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="(m, i) in config.mounts"
            :id="`mount-${i}`"
            :key="i"
            :data-access="m.read_only ? 'read-only' : 'read-write'"
            class="grid gap-1 py-3"
          >
            <p class="caption break-all">
              <code class="font-mono">{{ m.container_path ?? 'Not known' }}</code>
              from
              <code class="font-mono">{{ m.host_path ?? 'Not known' }}</code>
            </p>
            <AccessMark
              :read-write="!m.read_only"
              write-label="Read-write: the agent can change these files"
            />
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">No extra mounts.</p>
      </section>

      <section
        id="group-destinations"
        aria-labelledby="group-destinations-title"
        class="grid gap-3"
      >
        <h2 id="group-destinations-title" class="title-1">Who it may message</h2>
        <ul
          v-if="group.destinations.length"
          class="caption divide-y divide-line border-y border-line"
        >
          <li
            v-for="(d, i) in group.destinations"
            :id="`destination-${i}`"
            :key="i"
            class="py-3 break-words"
          >
            {{ destinationWords(d) }}
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">No destinations.</p>
      </section>
    </template>
  </div>
</template>
