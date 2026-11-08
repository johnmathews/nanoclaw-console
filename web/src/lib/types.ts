/**
 * The console API's answers, as docs/architecture.md §4.7 defines them. Every time is UTC ISO 8601
 * with milliseconds and `Z`; a field whose read failed is `null` and named in `sources`.
 */

/** One source's reads: `errors` maps a read (a broker verb, or a Loki query) to an error code. */
export type SourceState = { ok: boolean; errors: Record<string, string> }

/** `broker` is always present; `loki` only on views that read Loki (overview, problems). */
export type Sources = { broker: SourceState; loki?: SourceState }

export type ClaudeStatus = 'ok' | 'degraded' | 'failing' | 'unknown'

export type Severity = 'error' | 'warning' | 'info'

/** An item of `/api/problems`, and of the overview's `warnings`. */
export type ProblemItem = {
  kind: string
  severity: Severity
  title: string
  detail: string | null
  at: string | null
  count: number | null
  ref: { type: 'task' | 'group' | 'approval' | 'channel' | 'source'; id: string } | null
}

export type ClaudeHealth = {
  status: ClaudeStatus
  reasons: string[]
  last_agent_call: {
    at: string | null
    status: number | null
    agent: string | null
    injections_applied: number | null
  } | null
  last_success_at: string | null
  agent_calls_24h: number | null
  auth_failures_1h: number | null
  auth_failures_24h: number | null
  probe: {
    status: 'ok' | 'failing' | 'unknown'
    http_status: number | null
    checked_at: string | null
  } | null
}

export type NanoclawHealth =
  | { available: false; reason: 'not_answering' | 'broker_error' }
  | {
      available: true
      healthy: boolean | null
      uptime_seconds: number | null
      message_loop_running: boolean | null
      channels: { name: string | null; connected: boolean | null }[]
      queue: { active: number | null; max: number | null; waiting: number | null }
      registered_group_count: number | null
      active_session_count: number | null
      last_message_at: string | null
      tasks: {
        active_count: number | null
        paused_count: number | null
        next_run_at: string | null
        recent_failures: number | null
      }
    }

/** The host `~/.claude` login's weekly quota, never NanoClaw's token (D6): show `label` as is. */
export type Quota =
  | { available: false; reason: 'broker_error'; label: string }
  | {
      available: true
      label: string
      source: string
      weekly_pct: number | null
      resets_at: string | null
      resets_text: string | null
    }

export type Counts = {
  groups: number | null
  channels: number | null
  wirings: number | null
  sessions: number | null
  tasks: number | null
  tasks_paused: number | null
  tasks_overdue_on_resume: number | null
  pending_approvals: number | null
  dropped_messages: number | null
  host_errors_24h: number | null
  host_warnings_24h: number | null
}

/** GET /api/overview */
export type Overview = {
  generated_at: string
  claude: ClaudeHealth
  nanoclaw: NanoclawHealth
  quota: Quota
  counts: Counts
  warnings: ProblemItem[]
  sources: Sources
}

export type Schedule = {
  cron: string | null
  words: string | null
  timezone: string
  valid: boolean
  next_fire_at: string | null
}

export type Task = {
  id: string
  row_id: string | null
  group: { id: string | null; name: string | null; folder: string | null }
  status: string | null
  overdue_on_resume: boolean
  prompt: string | null
  task_file: string | null
  has_script: boolean
  schedule: Schedule
  next_run_at: string | null
  process_after: string | null
  last_run_at: string | null
  runs: number | null
  failed_runs: number | null
  tries: number | null
  series_started_at: string | null
  series_age_days: number | null
  occurrence_created_at: string | null
  session_id: string | null
}

/** GET /api/tasks */
export type TaskList = {
  generated_at: string
  timezone: string
  tasks: Task[]
  sources: Sources
}

/** GET /api/tasks/{id}: 404 `{"error": "not_found"}`, 503 `{"error": "broker_unavailable"}`. */
export type TaskDetail = {
  generated_at: string
  timezone: string
  task: Task & { recent_log: string[]; completed_runs: number | null }
  task_file: { name: string | null; content: string; truncated: boolean } | null
  sources: Sources
}
