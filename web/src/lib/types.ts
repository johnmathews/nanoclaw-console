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

/** A group as other answers name it: `name` is null when the group is not in `groups-list`. */
export type GroupRef = { id: string; name: string | null; folder?: string | null }

/** An MCP server: names and counts only, never a header, env or arg value (§4.7, B7). */
export type McpServer = {
  name: string
  type: string | null
  transport: string | null
  /** Already reduced by the broker to `scheme://host[:port]`. */
  url: string | null
  command: string | null
  header_names: string[]
  env_names: string[]
  arg_count: number
}

export type Mount = {
  host_path: string | null
  container_path: string | null
  read_only: boolean
}

export type GroupConfig = {
  model: string | null
  provider: string | null
  effort: string | null
  speed: string | null
  assistant_name: string | null
  cli_scope: string | null
  timezone: string | null
  image_tag: string | null
  max_messages_per_prompt: number | null
  skills: string | null
  packages_apt: string[]
  packages_npm: string[]
  updated_at: string | null
  mcp_servers: McpServer[]
  mounts: Mount[]
}

/** A wiring of a messaging group (a channel) to an agent group, with the channel's own policy. */
export type Channel = {
  wiring_id: string | null
  messaging_group_id: string | null
  name: string | null
  channel_type: string | null
  instance: string | null
  platform_id: string | null
  is_group: boolean | null
  engage_mode: string | null
  engage_pattern: string | null
  sender_scope: string | null
  ignored_message_policy: string | null
  unknown_sender_policy: string | null
  session_mode: string | null
  priority: number | null
  threads: string | number | null
  denied_at: string | null
}

export type Destination = {
  local_name: string | null
  display_name: string | null
  channel_type: string | null
  target_type: string | null
  target_id: string | null
  target_name: string | null
  created_at: string | null
}

export type Group = {
  id: string
  name: string | null
  folder: string | null
  created_at: string | null
  /** null when this group's `groups-config-get` failed. */
  config: GroupConfig | null
  channels: Channel[]
  destinations: Destination[]
  sessions: { total: number; running: number }
  tasks: { total: number; paused: number; overdue_on_resume: number }
}

export type UnwiredChannel = {
  id: string | null
  name: string | null
  channel_type: string | null
  instance: string | null
  platform_id: string | null
  unknown_sender_policy: string | null
  denied_at: string | null
}

/** GET /api/groups */
export type GroupsView = {
  generated_at: string
  groups: Group[]
  unwired_channels: UnwiredChannel[]
  sources: Sources
}

export type Role = {
  user_id: string | null
  user_name: string | null
  user_kind: string | null
  role: string | null
  scope: 'global' | 'group'
  group: GroupRef | null
  granted_at: string | null
  granted_by: string | null
}

export type Member = {
  user_id: string | null
  user_name: string | null
  user_kind: string | null
  group: GroupRef | null
  added_at: string | null
  added_by: string | null
}

export type PermissionDestination = Destination & { group: GroupRef | null }

export type MountAllowlist =
  | { available: false; reason: 'not_readable' | 'broker_error' }
  | {
      available: true
      allowed_roots: { path: string | null; read_write: boolean; description: string | null }[]
      blocked_patterns: string[]
      non_main_read_only: boolean | null
    }

export type Approval = {
  id: string | null
  action: string | null
  title: string | null
  status: string | null
  created_at: string | null
  expires_at: string | null
  age_days: number | null
  stale: boolean
  group: GroupRef | null
  session_id: string | null
}

/** GET /api/permissions */
export type PermissionsView = {
  generated_at: string
  roles: Role[]
  members: Member[]
  /**
   * The broker's rows as they come (B22's one exception, while the live table is empty). Their
   * shape is not in the contract, so the web app shows how many there are and no field of them.
   */
  policies: unknown[]
  destinations: PermissionDestination[]
  mount_allowlist: MountAllowlist
  approvals: Approval[]
  not_visible: { what: string; why: string }[]
  sources: Sources
}

export type HostLogGroup = {
  level: string
  message: string
  count: number
  first_at: string
  last_at: string
  /** The newest line, already masked and cut to 500 characters by the API (§4.5). */
  sample: string
}

/** GET /api/problems */
export type ProblemsView = {
  generated_at: string
  items: ProblemItem[]
  host_logs: {
    window_hours: number
    errors: number
    warnings: number
    truncated: boolean
    groups: HostLogGroup[]
  } | null
  sources: Sources
}
