/**
 * Mock answers for the console's API, shaped exactly as docs/architecture.md §4.7 (and the API's
 * tests) define them. The Vitest suites and the Playwright suite (e2e/) both use them, so a change
 * to the contract changes one file. Relative imports only: Playwright has no `@/` alias.
 *
 * The clock is 2026-11-08 14:30 UTC (15:30 CET). The two paused series are F9's: paused by hand
 * in May, so resuming either runs it once straight away.
 */
import type {
  Group,
  GroupsView,
  Overview,
  PermissionsView,
  ProblemItem,
  ProblemsView,
  Task,
  TaskDetail,
  TaskList,
} from '../lib/types'

export const NOW = '2026-11-08T14:30:00.000Z'

/**
 * A token as if broker redaction had missed it. It is planted only in fields the web app never
 * shows (extra keys on an MCP server, a group config, a channel, an approval, a policy row, a
 * problem item and a log group), and the secret-absence tests assert it reaches no page.
 */
export const PLANTED_TOKEN = 'Bearer PLANTED-SECRET-ui-7f3a9c2e'
export const PLANTED_MARK = 'PLANTED-SECRET'

/** Adds keys the contract does not have, as a broker that forgot to redact would. */
function plant<T extends object>(target: T, extra: Record<string, unknown>): T {
  return Object.assign(target, extra)
}

const MAIN = { id: 'ag-1779373702795-5wbiev', name: 'main-group', folder: 'main' }
const SERVER = { id: 'ag-1779373800001-k2j8sd', name: 'server-bot', folder: 'slack_server-bot' }

const documentationSummary: Task = {
  id: 'task-1778399790530-f2euaw',
  row_id: 'task-1779780323000-q81mzn',
  group: MAIN,
  status: 'paused',
  overdue_on_resume: true,
  prompt: 'Read /workspace/agent/tasks/documentation-summary.md and follow the instructions in it.',
  task_file: 'documentation-summary.md',
  has_script: false,
  schedule: {
    cron: '3 9 * * *',
    words: 'At 09:03 every day',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: '2026-11-09T08:03:00.000Z',
  },
  next_run_at: null,
  process_after: '2026-05-27T07:03:00.000Z',
  last_run_at: '2026-05-26T07:03:00.000Z',
  runs: 5,
  failed_runs: 0,
  tries: 0,
  series_started_at: '2026-05-10T07:56:30.530Z',
  series_age_days: 182,
  occurrence_created_at: '2026-05-26T07:05:23.000Z',
  session_id: 'sess-1779373704233-eu40dq',
}

const morningReport: Task = {
  ...documentationSummary,
  id: 'task-1779373800000-mr7c0d',
  row_id: 'task-1779771600000-mr7c0e',
  prompt: 'Read /workspace/agent/tasks/morning-report.md and follow the instructions in it.',
  task_file: 'morning-report.md',
  schedule: {
    cron: '0 8 * * *',
    words: 'At 08:00 every day',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: '2026-11-09T07:00:00.000Z',
  },
  process_after: '2026-05-27T06:00:00.000Z',
  last_run_at: '2026-05-26T06:00:00.000Z',
  runs: 9,
  series_started_at: '2026-05-21T14:30:00.000Z',
  series_age_days: 171,
}

const memoryReport: Task = {
  id: 'task-1783504800000-mh4k2p',
  row_id: 'task-1786544560667-a9d3f1',
  group: SERVER,
  status: 'pending',
  overdue_on_resume: false,
  prompt: 'Read /workspace/agent/tasks/memory-history-report.md and post the summary to #server.',
  task_file: 'memory-history-report.md',
  has_script: false,
  schedule: {
    cron: '0 17 * * *',
    words: 'At 17:00 every day',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: '2026-11-08T16:00:00.000Z',
  },
  next_run_at: '2026-11-08T16:00:00.000Z',
  process_after: '2026-11-08T16:00:00.000Z',
  last_run_at: '2026-11-07T16:00:41.000Z',
  runs: 123,
  failed_runs: 3,
  tries: 0,
  series_started_at: '2026-07-08T10:00:00.000Z',
  series_age_days: 123,
  occurrence_created_at: '2026-11-08T13:22:40.667Z',
  session_id: 'sess-1783504800100-x1c2v3',
}

const inboxCheck: Task = {
  id: 'task-1780000000000-ib9q2w',
  row_id: 'task-1786545120000-ib9q2x',
  group: SERVER,
  status: 'pending',
  overdue_on_resume: false,
  prompt:
    'Check the shared inbox for anything addressed to the server bot, summarise each new message in one line with its sender and subject, and reply in the thread only when a message asks a direct question that the runbooks answer.',
  task_file: null,
  has_script: true,
  schedule: {
    cron: '7,22,37,52 * * * *',
    words: 'At 7, 22, 37 and 52 minutes past every hour',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: '2026-11-08T14:37:00.000Z',
  },
  next_run_at: '2026-11-08T14:37:00.000Z',
  process_after: '2026-11-08T14:37:00.000Z',
  last_run_at: '2026-11-08T14:22:05.000Z',
  runs: 11846,
  failed_runs: 0,
  tries: 0,
  series_started_at: '2026-05-28T08:26:40.000Z',
  series_age_days: 164,
  occurrence_created_at: '2026-11-08T14:22:40.000Z',
  session_id: 'sess-1780000000100-ib0000',
}

const weeklyDigest: Task = {
  id: 'weekly-digest',
  row_id: 'task-1786540000000-wd0001',
  group: { id: 'ag-1779999999999-gone00', name: null, folder: null },
  status: 'pending',
  overdue_on_resume: false,
  prompt: 'Read /workspace/agent/tasks/weekly-digest.md and follow it.',
  task_file: 'weekly-digest.md',
  has_script: false,
  schedule: {
    cron: '0 9 * * 1',
    words: 'At 09:00 on Monday',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: '2026-11-09T08:00:00.000Z',
  },
  next_run_at: '2026-11-09T08:00:00.000Z',
  process_after: '2026-11-09T08:00:00.000Z',
  last_run_at: null,
  runs: 0,
  failed_runs: 0,
  tries: 0,
  series_started_at: null,
  series_age_days: null,
  occurrence_created_at: '2026-11-02T08:00:12.000Z',
  session_id: null,
}

const reminder: Task = {
  id: 'task-1786540800000-rm1nd3',
  row_id: 'task-1786540800000-rm1nd3',
  group: MAIN,
  status: 'pending',
  overdue_on_resume: false,
  prompt: 'Remind John to renew the Tailscale auth key.',
  task_file: null,
  has_script: false,
  schedule: {
    cron: null,
    words: 'Once',
    timezone: 'Europe/Amsterdam',
    valid: true,
    next_fire_at: null,
  },
  next_run_at: '2026-11-12T08:00:00.000Z',
  process_after: '2026-11-12T08:00:00.000Z',
  last_run_at: null,
  runs: 0,
  failed_runs: 0,
  tries: 0,
  series_started_at: '2026-11-07T09:20:00.000Z',
  series_age_days: 1,
  occurrence_created_at: '2026-11-07T09:20:00.000Z',
  session_id: 'sess-1779373704233-eu40dq',
}

/** Sorted as the API sorts them: by next run, paused (null) last. */
export const TASKS: Task[] = [
  inboxCheck,
  memoryReport,
  weeklyDigest,
  reminder,
  documentationSummary,
  morningReport,
]

export const PAUSED_TASK = documentationSummary

export function taskList(): TaskList {
  return {
    generated_at: NOW,
    timezone: 'Europe/Amsterdam',
    tasks: structuredClone(TASKS),
    sources: { broker: { ok: true, errors: {} } },
  }
}

const TASK_FILES: Record<string, string> = {
  'documentation-summary.md': [
    '# Documentation summary',
    '',
    'Every morning, read the journal entries added to the home-server repo since the last run and',
    'post a **five-line summary** to `#server`.',
    '',
    '1. List the new files under `journal/`.',
    '2. Summarise each in one line.',
    '3. Post the summary. If there is nothing new, post nothing.',
    '',
    '<script>alert("planted")</script>',
    '',
    '<img src="https://tracker.example/pixel.gif" alt="">',
    '',
    '[A planted link](javascript:alert(1)) and [the runbook](https://docs.example.com/runbook).',
  ].join('\n'),
}

export function taskDetail(id: string = PAUSED_TASK.id): TaskDetail {
  const task = structuredClone(TASKS.find((t) => t.id === id) ?? PAUSED_TASK)
  const content = task.task_file ? TASK_FILES[task.task_file] : undefined
  return {
    generated_at: NOW,
    timezone: 'Europe/Amsterdam',
    task: {
      ...task,
      recent_log:
        task.id === memoryReport.id
          ? [
              '2026-11-06T16:00:39Z ok Posted the memory history report (3 changes).',
              '2026-11-07T16:00:41Z error Slack refused the post: channel_not_found',
            ]
          : [],
      completed_runs: task.runs,
    },
    task_file: content !== undefined ? { name: task.task_file, content, truncated: false } : null,
    sources: { broker: { ok: true, errors: {} } },
  }
}

const WARNINGS: ProblemItem[] = [
  {
    kind: 'host_log_errors',
    severity: 'error',
    title: 'NanoClaw logged 8 errors in 24 hours',
    detail: 'Most frequent: Container exited with error (3).',
    at: '2026-11-08T13:58:02.000Z',
    count: 8,
    ref: null,
  },
  {
    kind: 'task_paused_overdue',
    severity: 'warning',
    title: 'documentation-summary.md is paused and overdue',
    detail: 'Resuming it runs it once straight away, then at 09:03 every day.',
    at: '2026-05-27T07:03:00.000Z',
    count: null,
    ref: { type: 'task', id: documentationSummary.id },
  },
  plant(
    {
      kind: 'approval_stale',
      severity: 'warning' as const,
      title: 'An approval has waited 147 days',
      detail: 'Change main-group config (cli_command).',
      at: '2026-06-14T10:12:00.000Z',
      count: null,
      ref: { type: 'approval' as const, id: 'appr-1781431920000-ab12cd' },
    },
    { payload: PLANTED_TOKEN },
  ),
  {
    kind: 'dropped_messages',
    severity: 'info',
    title: 'NanoClaw dropped 3 messages',
    detail: 'No agent is wired to the channel they came from.',
    at: '2026-11-07T19:40:00.000Z',
    count: 3,
    ref: { type: 'channel', id: 'mg-1780100000000-dr0p01' },
  },
]

export function overview(): Overview {
  return {
    generated_at: NOW,
    claude: {
      status: 'ok',
      reasons: ['The last agent call to Claude succeeded (HTTP 200).'],
      last_agent_call: {
        at: '2026-11-08T14:28:12.000Z',
        status: 200,
        agent: 'main-group',
        injections_applied: 1,
      },
      last_success_at: '2026-11-08T14:28:12.000Z',
      agent_calls_24h: 412,
      auth_failures_1h: 0,
      auth_failures_24h: 0,
      probe: { status: 'ok', http_status: 400, checked_at: '2026-11-08T14:26:00.000Z' },
    },
    nanoclaw: {
      available: true,
      healthy: true,
      uptime_seconds: 72739,
      message_loop_running: true,
      channels: [
        { name: 'cli', connected: true },
        { name: 'slack', connected: true },
      ],
      queue: { active: 1, max: 0, waiting: 0 },
      registered_group_count: 15,
      active_session_count: 18,
      last_message_at: '2026-11-08T13:37:45.983Z',
      tasks: {
        active_count: 14,
        paused_count: 2,
        next_run_at: '2026-11-08T14:37:00.000Z',
        recent_failures: 0,
      },
    },
    quota: {
      available: true,
      label: "Weekly quota of the host's ~/.claude login (not NanoClaw's token)",
      source: 'host ~/.claude login',
      weekly_pct: 39,
      resets_at: '2026-11-10T20:00:00.000Z',
      resets_text: 'Nov 10, 9pm (Europe/Amsterdam)',
    },
    counts: {
      groups: 15,
      channels: 17,
      wirings: 14,
      sessions: 80,
      tasks: 16,
      tasks_paused: 2,
      tasks_overdue_on_resume: 2,
      pending_approvals: 1,
      dropped_messages: 3,
      host_errors_24h: 8,
      host_warnings_24h: 13,
    },
    warnings: structuredClone(WARNINGS),
    sources: { broker: { ok: true, errors: {} }, loki: { ok: true, errors: {} } },
  }
}

/** The overview when NanoClaw's /health and Loki did not answer: the degraded shape. */
export function overviewDegraded(): Overview {
  const o = overview()
  o.claude = {
    status: 'unknown',
    reasons: ['No agent call to Claude in the last 24 hours, and the probe did not answer.'],
    last_agent_call: null,
    last_success_at: null,
    agent_calls_24h: null,
    auth_failures_1h: null,
    auth_failures_24h: null,
    probe: null,
  }
  o.nanoclaw = { available: false, reason: 'not_answering' }
  o.quota = { available: false, reason: 'broker_error', label: o.quota.label }
  o.counts.host_errors_24h = null
  o.counts.host_warnings_24h = null
  o.warnings = []
  o.sources = {
    broker: { ok: false, errors: { usage: 'timeout' } },
    loki: { ok: false, errors: { claude: 'unavailable', host_logs: 'unavailable' } },
  }
  return o
}

// -- W9: groups, permissions, problems ------------------------------------------------------------

const INTRO = { id: 'ag-1781000000000-in7r0s', name: 'introspection', folder: 'introspection' }

/** The ids the problems and overview fixtures point at, so their links land on something. */
export const STALE_APPROVAL_ID = 'appr-1781431920000-ab12cd'
export const UNWIRED_CHANNEL_ID = 'mg-1780100000000-dr0p01'

function mainGroup(): Group {
  return {
    id: MAIN.id,
    name: MAIN.name,
    folder: MAIN.folder,
    created_at: '2026-05-21T13:42:16.391Z',
    config: plant(
      {
        model: 'claude-opus-4-7',
        provider: null,
        effort: 'high',
        speed: null,
        assistant_name: 'Claw',
        cli_scope: 'group',
        timezone: null,
        image_tag: null,
        max_messages_per_prompt: 40,
        skills: 'all',
        packages_apt: ['ripgrep'],
        packages_npm: [],
        updated_at: '2026-11-07T14:21:00.890Z',
        mcp_servers: [
          plant(
            {
              name: 'journal',
              type: 'http',
              transport: null,
              url: 'https://journal.example.internal:8443',
              command: null,
              header_names: ['Authorization'],
              env_names: [],
              arg_count: 0,
            },
            { headers: { Authorization: PLANTED_TOKEN } },
          ),
          plant(
            {
              name: 'parallel-search',
              type: 'http',
              transport: 'streamable-http',
              url: 'https://search.parallel.example',
              command: null,
              header_names: ['Authorization', 'X-Client'],
              env_names: [],
              arg_count: 0,
            },
            { headers: { Authorization: PLANTED_TOKEN }, token: PLANTED_TOKEN },
          ),
          plant(
            {
              name: 'files',
              type: 'stdio',
              transport: null,
              url: null,
              command: '/usr/local/bin/mcp-files',
              header_names: [],
              env_names: ['FILES_TOKEN'],
              arg_count: 2,
            },
            { env: { FILES_TOKEN: PLANTED_TOKEN }, args: ['--token', PLANTED_TOKEN] },
          ),
        ],
        mounts: [
          {
            host_path: '/srv/media/notes',
            container_path: '/workspace/extra/notes',
            read_only: true,
          },
          {
            host_path: '/srv/apps/nanoclaw/groups/main/scratch',
            container_path: '/workspace/extra/scratch',
            read_only: false,
          },
        ],
      },
      { env: { ANTHROPIC_API_KEY: PLANTED_TOKEN } },
    ),
    channels: [
      plant(
        {
          wiring_id: 'mga-1779373703000-w1main',
          messaging_group_id: 'mg-1779373702900-slkdm1',
          name: 'John (DM)',
          channel_type: 'slack',
          instance: 'slack',
          platform_id: 'slack:D07ABCDEF12',
          is_group: false,
          engage_mode: 'pattern',
          engage_pattern: '.',
          sender_scope: 'all',
          ignored_message_policy: 'drop',
          unknown_sender_policy: 'strict',
          session_mode: 'shared',
          priority: 0,
          threads: null,
          denied_at: null,
        },
        { webhook_url: `https://hooks.example.com/services/x?auth=${PLANTED_TOKEN}` },
      ),
      {
        wiring_id: 'mga-1779373703001-w2cli',
        messaging_group_id: 'mg-1779373702901-cli001',
        name: 'Terminal',
        channel_type: 'cli',
        instance: 'cli',
        platform_id: 'cli:local',
        is_group: false,
        engage_mode: 'mention',
        engage_pattern: null,
        sender_scope: 'known',
        ignored_message_policy: 'accumulate',
        unknown_sender_policy: 'request_approval',
        session_mode: 'per-thread',
        priority: 1,
        threads: 1,
        denied_at: null,
      },
    ],
    destinations: [
      {
        local_name: 'server',
        display_name: '#server',
        channel_type: 'slack',
        target_type: 'channel',
        target_id: 'mg-1779373800100-srv001',
        target_name: '#server',
        created_at: '2026-05-21T14:28:22.792Z',
      },
      {
        local_name: 'server-bot',
        display_name: 'server-bot',
        channel_type: null,
        target_type: 'agent',
        target_id: SERVER.id,
        target_name: 'server-bot',
        created_at: '2026-05-22T09:00:00.000Z',
      },
    ],
    sessions: { total: 6, running: 1 },
    tasks: { total: 3, paused: 2, overdue_on_resume: 2 },
  }
}

function serverGroup(): Group {
  return {
    id: SERVER.id,
    name: SERVER.name,
    folder: SERVER.folder,
    created_at: '2026-05-21T14:28:22.000Z',
    config: {
      model: 'claude-sonnet-4-6',
      provider: 'anthropic',
      effort: null,
      speed: null,
      assistant_name: null,
      cli_scope: 'group',
      timezone: 'Europe/Amsterdam',
      image_tag: 'nanoclaw-agent:latest',
      max_messages_per_prompt: null,
      skills: null,
      packages_apt: [],
      packages_npm: ['@modelcontextprotocol/sdk'],
      updated_at: '2026-10-30T08:00:00.000Z',
      mcp_servers: [],
      mounts: [
        {
          host_path: '/srv/runbooks',
          container_path: '/workspace/extra/runbooks',
          read_only: true,
        },
      ],
    },
    channels: [
      {
        wiring_id: 'mga-1779373800200-w3srv',
        messaging_group_id: 'mg-1779373800100-srv001',
        name: '#server',
        channel_type: 'slack',
        instance: 'slack',
        platform_id: 'slack:C07SERVER01',
        is_group: true,
        engage_mode: 'mention-sticky',
        engage_pattern: null,
        sender_scope: 'all',
        ignored_message_policy: 'drop',
        unknown_sender_policy: 'decline_notify',
        session_mode: 'agent-shared',
        priority: 0,
        threads: 'auto',
        denied_at: null,
      },
    ],
    destinations: [],
    sessions: { total: 3, running: 0 },
    tasks: { total: 3, paused: 0, overdue_on_resume: 0 },
  }
}

function introspectionGroup(): Group {
  return {
    id: INTRO.id,
    name: INTRO.name,
    folder: INTRO.folder,
    created_at: '2026-07-01T10:00:00.000Z',
    config: {
      model: 'claude-haiku-4-5',
      provider: null,
      effort: null,
      speed: 'fast',
      assistant_name: null,
      cli_scope: 'global',
      timezone: null,
      image_tag: null,
      max_messages_per_prompt: null,
      skills: null,
      packages_apt: [],
      packages_npm: [],
      updated_at: null,
      mcp_servers: [],
      mounts: [
        {
          host_path: '/srv/apps/nanoclaw',
          container_path: '/workspace/nanoclaw',
          read_only: false,
        },
      ],
    },
    channels: [],
    destinations: [],
    sessions: { total: 0, running: 0 },
    tasks: { total: 0, paused: 0, overdue_on_resume: 0 },
  }
}

export const GROUP_IDS = { main: MAIN.id, server: SERVER.id, introspection: INTRO.id }

export function groupsView(): GroupsView {
  return {
    generated_at: NOW,
    groups: [mainGroup(), serverGroup(), introspectionGroup()],
    unwired_channels: [
      plant(
        {
          id: UNWIRED_CHANNEL_ID,
          name: '#random',
          channel_type: 'slack',
          instance: 'slack',
          platform_id: 'slack:C07RANDOM01',
          unknown_sender_policy: 'public',
          denied_at: null,
        },
        { webhook_url: `https://hooks.example.com/${PLANTED_TOKEN}` },
      ),
      {
        id: 'mg-1780200000000-dn1ed0',
        name: null,
        channel_type: 'whatsapp',
        instance: 'whatsapp',
        platform_id: 'whatsapp:31600000000',
        unknown_sender_policy: 'strict',
        denied_at: '2026-06-02T18:30:00.000Z',
      },
    ],
    sources: { broker: { ok: true, errors: {} } },
  }
}

const OWNER_ID = 'slack:U07JOHN0001'

export function permissionsView(): PermissionsView {
  return {
    generated_at: NOW,
    roles: [
      {
        user_id: OWNER_ID,
        user_name: 'John',
        user_kind: 'slack',
        role: 'owner',
        scope: 'global',
        group: null,
        granted_at: '2026-05-26T09:50:07.000Z',
        granted_by: null,
      },
      {
        user_id: 'whatsapp:31600000001',
        user_name: null,
        user_kind: null,
        role: 'owner',
        scope: 'global',
        group: null,
        granted_at: '2026-05-21T15:10:18.079Z',
        granted_by: null,
      },
      {
        user_id: 'slack:U07SARA0002',
        user_name: 'Sara',
        user_kind: 'slack',
        role: 'admin',
        scope: 'group',
        group: { id: SERVER.id, name: SERVER.name },
        granted_at: '2026-09-01T12:00:00.000Z',
        granted_by: OWNER_ID,
      },
    ],
    members: [
      {
        user_id: 'slack:U07SARA0002',
        user_name: 'Sara',
        user_kind: 'slack',
        group: { id: SERVER.id, name: SERVER.name },
        added_at: '2026-11-07T14:21:00.890Z',
        added_by: OWNER_ID,
      },
      {
        user_id: OWNER_ID,
        user_name: 'John',
        user_kind: 'slack',
        group: { id: 'ag-1779999999999-gone00', name: null },
        added_at: '2026-05-30T10:30:54.845Z',
        added_by: null,
      },
    ],
    policies: [
      plant({ id: 'pol-1', note: 'shape not in the contract' }, { secret: PLANTED_TOKEN }),
    ],
    destinations: [
      ...mainGroup().destinations.map((d) => ({ group: { id: MAIN.id, name: MAIN.name }, ...d })),
      {
        group: { id: 'ag-1779999999999-gone00', name: null },
        local_name: 'old',
        display_name: null,
        channel_type: 'slack',
        target_type: 'channel',
        target_id: 'mg-1779000000000-old000',
        target_name: null,
        created_at: null,
      },
    ],
    mount_allowlist: {
      available: true,
      allowed_roots: [
        { path: '/srv/media', read_write: false, description: 'Media library, read only' },
        { path: '/srv/apps/nanoclaw', read_write: true, description: 'NanoClaw itself' },
        { path: '/srv/runbooks', read_write: false, description: null },
      ],
      blocked_patterns: ['.ssh', '.env', 'credentials'],
      non_main_read_only: true,
    },
    approvals: [
      plant(
        {
          id: STALE_APPROVAL_ID,
          action: 'cli_command',
          title: 'Change main-group config',
          status: 'pending',
          created_at: '2026-06-14T10:12:00.000Z',
          expires_at: null,
          age_days: 147,
          stale: true,
          group: null,
          session_id: 'sess-1779373704233-eu40dq',
        },
        { payload: `{"frame":{"args":{"header":"${PLANTED_TOKEN}"}}}` },
      ),
      {
        id: 'appr-1786540000000-fr3sh0',
        action: 'install_packages',
        title: 'Install jq',
        status: 'pending',
        created_at: '2026-11-08T12:00:00.000Z',
        expires_at: '2026-11-09T12:00:00.000Z',
        age_days: 0,
        stale: false,
        group: { id: SERVER.id, name: SERVER.name },
        session_id: null,
      },
    ],
    not_visible: [
      plant(
        {
          what: 'Per-group environment variables',
          why: "ncl leaves env out of a group's config, and the console never reads NanoClaw's database or .env.",
        },
        { values: { ANTHROPIC_API_KEY: PLANTED_TOKEN } },
      ),
      {
        what: 'OneCLI secret assignments',
        why: "They live in OneCLI's vault; the console has no access to OneCLI.",
      },
      {
        what: 'Egress lockdown',
        why: "It is an environment setting of NanoClaw's and a Docker network; the broker has neither the Docker socket nor .env.",
      },
    ],
    sources: { broker: { ok: true, errors: {} } },
  }
}

/** The problems a normal day has, sorted as the API sorts them (severity, undated first, newest). */
export function problemsView(): ProblemsView {
  const items: ProblemItem[] = [
    {
      kind: 'host_log_errors',
      severity: 'error',
      title: 'NanoClaw logged 8 errors in 24 hours',
      detail: 'Most frequent: Container exited with error (3).',
      at: '2026-11-08T13:58:02.000Z',
      count: 8,
      ref: null,
    },
    {
      kind: 'host_log_warnings',
      severity: 'warning',
      title: 'NanoClaw logged 13 warnings in 24 hours',
      detail: 'Most frequent: MESSAGE DROPPED (9).',
      at: '2026-11-08T14:10:00.000Z',
      count: 13,
      ref: null,
    },
    {
      kind: 'claude_auth_failures',
      severity: 'warning',
      title: '2 calls to Claude refused (401 or 403) in 24 hours',
      detail: '0 in the last hour.',
      at: null,
      count: 2,
      ref: null,
    },
    {
      kind: 'task_failures',
      severity: 'warning',
      title: 'memory-history-report.md has 3 failed runs',
      detail: null,
      at: '2026-11-07T16:00:41.000Z',
      count: 3,
      ref: { type: 'task', id: 'task-1783504800000-mh4k2p' },
    },
    plant(
      {
        kind: 'approval_stale',
        severity: 'warning' as const,
        title: 'An approval has waited 147 days',
        detail: 'Change main-group config (cli_command).',
        at: '2026-06-14T10:12:00.000Z',
        count: null,
        ref: { type: 'approval' as const, id: STALE_APPROVAL_ID },
      },
      { payload: PLANTED_TOKEN },
    ),
    {
      kind: 'task_paused_overdue',
      severity: 'warning',
      title: 'morning-report.md is paused and overdue',
      detail: 'Resuming it runs it once straight away, then at 08:00 every day.',
      at: '2026-05-27T06:00:00.000Z',
      count: null,
      ref: { type: 'task', id: 'task-1779373800000-mr7c0d' },
    },
    {
      kind: 'task_paused_overdue',
      severity: 'warning',
      title: 'documentation-summary.md is paused and overdue',
      detail: 'Resuming it runs it once straight away, then at 09:03 every day.',
      at: '2026-05-27T07:03:00.000Z',
      count: null,
      ref: { type: 'task', id: 'task-1778399790530-f2euaw' },
    },
    {
      kind: 'dropped_messages',
      severity: 'info',
      title: '3 messages dropped: no agent wired',
      detail: `Channel ${UNWIRED_CHANNEL_ID} (slack).`,
      at: '2026-11-07T19:40:00.000Z',
      count: 3,
      ref: { type: 'channel', id: UNWIRED_CHANNEL_ID },
    },
  ]
  return {
    generated_at: NOW,
    items,
    host_logs: {
      window_hours: 24,
      errors: 8,
      warnings: 13,
      truncated: false,
      groups: [
        plant(
          {
            level: 'ERROR',
            message: 'Container exited with error',
            count: 3,
            first_at: '2026-11-08T02:11:40.000Z',
            last_at: '2026-11-08T13:58:02.000Z',
            sample:
              '[14:58:02.117] ERROR Container exited with error code=137 group="main-group" url=https://api.example.com authorization=*** detail="the agent container ran out of memory while it was summarising a very long thread, and the host restarted it"',
          },
          { raw: `authorization: ${PLANTED_TOKEN}` },
        ),
        {
          level: 'ERROR',
          message: 'Slack delivery failed',
          count: 5,
          first_at: '2026-11-07T16:00:41.000Z',
          last_at: '2026-11-08T09:12:00.000Z',
          sample: '[10:12:00.004] ERROR Slack delivery failed error="channel_not_found"',
        },
        {
          level: 'WARN',
          message: 'MESSAGE DROPPED',
          count: 9,
          first_at: '2026-11-07T19:40:00.000Z',
          last_at: '2026-11-08T14:10:00.000Z',
          sample: `[15:10:00.500] WARN MESSAGE DROPPED reason=no_agent_wired mg="${UNWIRED_CHANNEL_ID}"`,
        },
        {
          level: 'WARN',
          message: 'Inserted next recurrence',
          count: 4,
          first_at: '2026-11-08T06:00:00.000Z',
          last_at: '2026-11-08T08:03:00.000Z',
          sample: '[09:03:00.010] WARN Inserted next recurrence originalId="…" seriesId="…"',
        },
      ],
    },
    sources: { broker: { ok: true, errors: {} }, loki: { ok: true, errors: {} } },
  }
}

/**
 * One item of every kind the contract names (§4.7), sorted as the API sorts them, plus one
 * `group_note`: no kind sends a `group` ref yet, but the contract allows it, and an unknown kind
 * must draw like any other.
 */
export function problemsEveryKind(): ProblemsView {
  const base = problemsView()
  const item = (
    kind: string,
    severity: ProblemItem['severity'],
    title: string,
    ref: ProblemItem['ref'] = null,
    at: string | null = null,
  ): ProblemItem => ({ kind, severity, title, detail: null, at, count: null, ref })
  base.items = [
    item('source_unavailable', 'error', 'The broker did not answer every read', {
      type: 'source',
      id: 'broker',
    }),
    item('source_unavailable', 'error', 'Loki did not answer', { type: 'source', id: 'loki' }),
    item('claude_failing', 'error', 'Claude is failing'),
    item('nanoclaw_not_answering', 'error', "NanoClaw's health endpoint did not answer"),
    item('nanoclaw_unhealthy', 'error', 'NanoClaw reports itself unhealthy'),
    item('channel_disconnected', 'error', 'Channel slack is not connected', {
      type: 'channel',
      id: 'slack',
    }),
    item('message_loop_stopped', 'error', "NanoClaw's message loop is not running"),
    item(
      'claude_auth_failures',
      'error',
      '4 calls to Claude refused (401 or 403) in 24 hours',
      null,
      null,
    ),
    item(
      'host_log_errors',
      'error',
      'NanoClaw logged 8 errors in 24 hours',
      null,
      base.items[0]!.at,
    ),
    item('claude_degraded', 'warning', 'Claude is degraded'),
    item('host_log_warnings', 'warning', 'NanoClaw logged 13 warnings in 24 hours', null, NOW),
    item(
      'task_failures',
      'warning',
      'memory-history-report.md has 3 failed runs',
      {
        type: 'task',
        id: 'task-1783504800000-mh4k2p',
      },
      '2026-11-07T16:00:41.000Z',
    ),
    item(
      'approval_stale',
      'warning',
      'An approval has waited 147 days',
      {
        type: 'approval',
        id: STALE_APPROVAL_ID,
      },
      '2026-06-14T10:12:00.000Z',
    ),
    item(
      'task_paused_overdue',
      'warning',
      'documentation-summary.md is paused and overdue',
      {
        type: 'task',
        id: 'task-1778399790530-f2euaw',
      },
      '2026-05-27T07:03:00.000Z',
    ),
    item('claude_unknown', 'info', "Claude's health is unknown"),
    item(
      'dropped_messages',
      'info',
      '3 messages dropped: no agent wired',
      {
        type: 'channel',
        id: UNWIRED_CHANNEL_ID,
      },
      '2026-11-07T19:40:00.000Z',
    ),
    item(
      'group_note',
      'info',
      'A group needs a look',
      { type: 'group', id: MAIN.id },
      '2026-11-01T10:00:00.000Z',
    ),
  ]
  base.sources = {
    broker: { ok: false, errors: { health: 'unavailable' } },
    loki: { ok: false, errors: { claude: 'timeout' } },
  }
  return base
}
