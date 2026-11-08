/**
 * Mock answers for the console's API, shaped exactly as docs/architecture.md §4.7 (and the API's
 * tests) define them. The Vitest suites and the Playwright suite (e2e/) both use them, so a change
 * to the contract changes one file. Relative imports only: Playwright has no `@/` alias.
 *
 * The clock is 2026-11-08 14:30 UTC (15:30 CET). The two paused series are F9's: paused by hand
 * in May, so resuming either runs it once straight away.
 */
import type { Overview, ProblemItem, Task, TaskDetail, TaskList } from '../lib/types'

export const NOW = '2026-11-08T14:30:00.000Z'

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
  {
    kind: 'approval_stale',
    severity: 'warning',
    title: 'An approval has waited 147 days',
    detail: 'Change main-group config (cli_command).',
    at: '2026-06-14T10:12:00.000Z',
    count: null,
    ref: { type: 'approval', id: 'appr-1781431920000-ab12cd' },
  },
  {
    kind: 'dropped_messages',
    severity: 'info',
    title: 'NanoClaw dropped 3 messages',
    detail: 'No agent is wired to the channel they came from.',
    at: '2026-11-07T19:40:00.000Z',
    count: 3,
    ref: null,
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
