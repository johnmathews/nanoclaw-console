<script setup lang="ts">
import { computed, ref } from 'vue'
import AccessMark from '@/components/ui/AccessMark.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import PageStatus from '@/components/PageStatus.vue'
import TimeText from '@/components/TimeText.vue'
import { useApi } from '@/composables/useApi'
import { useHashTarget } from '@/composables/useHashTarget'
import { usePageTitle } from '@/composables/usePageTitle'
import { domId } from '@/lib/groups'
import { permissionsAnswer, personName, roleWords } from '@/lib/permissions'
import type { GroupRef, PermissionDestination, PermissionsView } from '@/lib/types'
import { countWords, humanise } from '@/lib/words'

/**
 * Who may do what (question 4): owners and admins, members, agent-to-agent policies, who may
 * message whom, the mount allowlist, approvals waiting (stale ones flagged, F19), and what the
 * console cannot see (F21). Every row is picked field by field; `policies` is counted only, since
 * its shape is not in the contract (B22).
 */
usePageTitle(() => 'Permissions')
const { data, error, checkedAt } = useApi<PermissionsView>(ref('/api/permissions'))
useHashTarget(computed(() => data.value !== null))

const answer = computed(() => (data.value ? permissionsAnswer(data.value) : null))
const failed = computed(() => data.value?.sources.broker.errors ?? {})

function groupLabel(g: GroupRef | null): string {
  return g ? (g.name ?? g.id) : 'no group'
}

function destinationWords(d: PermissionDestination): string {
  const target = d.target_name ?? d.target_id ?? 'an unknown target'
  const kind =
    d.target_type === 'agent'
      ? 'an agent'
      : d.target_type === 'channel'
        ? `a ${d.channel_type ? `${d.channel_type} ` : ''}channel`
        : (d.target_type ?? 'unknown kind')
  return `may message ${target} (${kind}) as ${d.local_name ?? 'unnamed'}`
}

const policiesSummary = computed(() => {
  const n = data.value?.policies.length ?? 0
  if (!n)
    return 'policies-list' in failed.value
      ? 'Couldn’t read the policies.'
      : 'No agent-to-agent policies.'
  return `${countWords(n, 'policy', 'policies')}. The console doesn’t show ${n === 1 ? 'its' : 'their'} fields yet; ncl policies list does.`
})
</script>

<template>
  <div id="permissions-page" class="grid gap-10">
    <header class="grid gap-3">
      <h1 class="display">Permissions</h1>
      <p v-if="answer" id="permissions-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="data">
      <section id="roles" aria-labelledby="roles-title" class="grid gap-3">
        <h2 id="roles-title" class="title-1">Owners and admins</h2>
        <ul v-if="data.roles.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="(r, i) in data.roles"
            :id="`role-${i}`"
            :key="i"
            class="grid gap-1 py-3 break-words"
          >
            <p class="body">
              <span class="font-semibold">{{ personName(r) }}</span>
              <span class="caption text-ink-secondary">
                {{ r.user_kind ?? '' }}
                <code v-if="r.user_id && r.user_name" class="font-mono break-all">{{
                  r.user_id
                }}</code></span
              >
            </p>
            <p class="caption">
              <template v-if="r.scope === 'group' && r.group"
                >{{ r.role ? humanise(r.role) : 'Unknown role' }} of
                <RouterLink
                  :to="`/groups/${r.group.id}`"
                  class="underline underline-offset-[3px] hover:decoration-2"
                  >{{ groupLabel(r.group) }}</RouterLink
                ></template
              ><template v-else>{{ roleWords(r) }}</template>
            </p>
            <p class="caption text-ink-secondary">
              <template v-if="r.granted_at"
                >Granted <TimeText :at="r.granted_at" :now="checkedAt"
              /></template>
              <template v-else>Granted at a time not known</template>
              <template v-if="r.granted_by">
                · granted by <code class="font-mono break-all">{{ r.granted_by }}</code></template
              >
            </p>
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">
          {{ 'roles-list' in failed ? 'Couldn’t read the roles.' : 'No owners or admins.' }}
        </p>
      </section>

      <section id="members" aria-labelledby="members-title" class="grid gap-3">
        <h2 id="members-title" class="title-1">Members</h2>
        <p class="body">A member may talk to a group whose channels admit known users only.</p>
        <ul v-if="data.members.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="(m, i) in data.members"
            :id="`member-${i}`"
            :key="i"
            class="grid gap-1 py-3 break-words"
          >
            <p class="body">
              <span class="font-semibold">{{ personName(m) }}</span>
              <span class="caption text-ink-secondary">
                {{ m.user_kind ?? '' }}
                <code v-if="m.user_id && m.user_name" class="font-mono break-all">{{
                  m.user_id
                }}</code></span
              >
            </p>
            <p class="caption">
              Member of
              <RouterLink
                v-if="m.group?.name"
                :to="`/groups/${m.group.id}`"
                class="underline underline-offset-[3px] hover:decoration-2"
                >{{ m.group.name }}</RouterLink
              ><code v-else class="font-mono break-all">{{ groupLabel(m.group) }}</code>
            </p>
            <p v-if="m.added_at || m.added_by" class="caption text-ink-secondary">
              <template v-if="m.added_at"
                >Added <TimeText :at="m.added_at" :now="checkedAt"
              /></template>
              <template v-if="m.added_by"> by {{ m.added_by }}</template>
            </p>
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">
          {{ 'members-list' in failed ? 'Couldn’t read the members.' : 'No group memberships.' }}
        </p>
      </section>

      <section id="policies" aria-labelledby="policies-title" class="grid gap-3">
        <h2 id="policies-title" class="title-1">Agent-to-agent policies</h2>
        <p id="policies-summary" class="body">{{ policiesSummary }}</p>
      </section>

      <section id="destinations" aria-labelledby="destinations-title" class="grid gap-3">
        <h2 id="destinations-title" class="title-1">Who may message whom</h2>
        <ul
          v-if="data.destinations.length"
          class="caption divide-y divide-line border-y border-line"
        >
          <li
            v-for="(d, i) in data.destinations"
            :id="`perm-destination-${i}`"
            :key="i"
            class="py-3 break-words"
          >
            <RouterLink
              v-if="d.group?.name"
              :to="`/groups/${d.group.id}`"
              class="font-semibold underline underline-offset-[3px] hover:decoration-2"
              >{{ d.group.name }}</RouterLink
            ><code v-else class="font-mono break-all">{{ groupLabel(d.group) }}</code>
            {{ destinationWords(d) }}
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">
          {{
            'destinations-list' in failed ? 'Couldn’t read the destinations.' : 'No destinations.'
          }}
        </p>
      </section>

      <section id="mount-allowlist" aria-labelledby="mount-allowlist-title" class="grid gap-3">
        <h2 id="mount-allowlist-title" class="title-1">Mount allowlist</h2>
        <template v-if="data.mount_allowlist.available">
          <p class="body">A group may mount only paths under these roots.</p>
          <ul
            v-if="data.mount_allowlist.allowed_roots.length"
            class="divide-y divide-line border-y border-line"
          >
            <li
              v-for="(root, i) in data.mount_allowlist.allowed_roots"
              :id="`allowed-root-${i}`"
              :key="i"
              :data-access="root.read_write ? 'read-write' : 'read-only'"
              class="grid gap-1 py-3"
            >
              <code class="caption font-mono break-all">{{ root.path ?? 'Not known' }}</code>
              <p v-if="root.description" class="caption text-ink-secondary">
                {{ root.description }}
              </p>
              <AccessMark :read-write="root.read_write" write-label="Read-write allowed" />
            </li>
          </ul>
          <p v-else class="body text-ink-secondary">No roots: no group may mount anything.</p>
          <p class="caption">
            Never mounted, whatever the root:
            <span id="blocked-patterns"
              ><template v-for="(p, i) in data.mount_allowlist.blocked_patterns" :key="p"
                >{{ i ? ' ' : '' }}<code class="font-mono">{{ p }}</code></template
              ></span
            >
            <template v-if="!data.mount_allowlist.blocked_patterns.length">nothing listed</template>
          </p>
          <p id="non-main-read-only" class="caption">
            <template v-if="data.mount_allowlist.non_main_read_only === true"
              >Groups other than main get read-only mounts, whatever a root allows.</template
            >
            <template v-else-if="data.mount_allowlist.non_main_read_only === false"
              >Groups other than main may get read-write mounts where a root allows it.</template
            >
            <template v-else>Whether other groups get read-only mounts is not set.</template>
          </p>
        </template>
        <InlineMessage
          v-else-if="data.mount_allowlist.reason === 'not_readable'"
          id="mount-allowlist-unread"
          tone="caution"
        >
          The broker couldn’t read the allowlist file on the host. Without it, NanoClaw allows no
          extra mounts.
        </InlineMessage>
        <InlineMessage v-else id="mount-allowlist-unread" tone="error">
          Couldn’t read the mount allowlist. It retries every 30 seconds.
        </InlineMessage>
      </section>

      <section id="approvals" aria-labelledby="approvals-title" class="grid gap-3">
        <h2 id="approvals-title" class="title-1">Approvals</h2>
        <ul v-if="data.approvals.length" class="divide-y divide-line border-y border-line">
          <li
            v-for="(a, i) in data.approvals"
            :id="a.id ? `approval-${domId(a.id)}` : `approval-${i}`"
            :key="a.id ?? i"
            :data-stale="String(a.stale)"
            class="grid gap-1 py-3 break-words"
          >
            <p class="body font-semibold">{{ a.title ?? 'Untitled' }}</p>
            <p class="caption text-ink-secondary">
              {{ a.status ? humanise(a.status) : 'Status not known' }}
              ·
              <code class="font-mono">{{ a.action ?? 'unknown action' }}</code>
              <template v-if="a.group">
                · for
                <RouterLink
                  :to="`/groups/${a.group.id}`"
                  class="text-ink underline underline-offset-[3px] hover:decoration-2"
                  >{{ groupLabel(a.group) }}</RouterLink
                ></template
              >
            </p>
            <p class="caption">
              <template v-if="a.created_at"
                >Asked <TimeText :at="a.created_at" :now="checkedAt" relative
              /></template>
              <template v-if="a.expires_at">
                · Expires <TimeText :at="a.expires_at" :now="checkedAt"
              /></template>
            </p>
            <InlineMessage v-if="a.stale" tone="caution">
              Waiting {{ a.age_days }} days{{ a.expires_at ? '.' : ', and it never expires.' }}
            </InlineMessage>
          </li>
        </ul>
        <p v-else class="body text-ink-secondary">
          {{
            'approvals-list' in failed
              ? 'Couldn’t read the approvals.'
              : 'No approvals are waiting.'
          }}
        </p>
      </section>

      <section
        id="not-visible"
        aria-labelledby="not-visible-title"
        class="grid gap-4 rounded-lg border border-line bg-panel p-4 shadow-overlay sm:p-6"
      >
        <h2 id="not-visible-title" class="title-2">Not visible to the console</h2>
        <p class="caption">
          These also decide what an agent may do, but the console cannot read them. Look in
          <code class="font-mono">ncl</code> or on the agent host.
        </p>
        <ul class="grid gap-3">
          <li v-for="(n, i) in data.not_visible" :id="`not-visible-${i}`" :key="i" class="grid">
            <p class="body font-semibold">{{ n.what }}</p>
            <p class="caption text-ink-secondary">{{ n.why }}</p>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
