"""The view payloads (docs/architecture.md §4.7).

Each view makes its broker and Loki reads in parallel and answers with whatever arrived: a field
whose read failed is null or empty, and `sources` names the failed reads and their codes. Every
field is picked by name, so a value the broker should have redacted but did not (an MCP header,
an env value, a task script, an approval payload) never reaches the web app.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .broker_client import BrokerClient, BrokerError
from .claude import ClaudeSignals, claude_status, read_signals
from .host_logs import WINDOW_HOURS, HostLogs, read_host_logs
from .loki import LokiClient, LokiError
from .schedule import (
    describe_schedule,
    iso,
    overdue_on_resume,
    parse_time,
    series_started_at,
    task_file_name,
)
from .ttl_cache import TtlCache

QUOTA_LABEL = "Weekly quota of the host's ~/.claude login (not NanoClaw's token)"
QUOTA_SOURCE = "host ~/.claude login"
STALE_APPROVAL = timedelta(days=7)
_NOT_SCHEDULED = frozenset({"paused", "completed", "cancelled", "canceled", "failed", "done"})
_SEVERITY = {"error": 0, "warning": 1, "info": 2}
_PROBE_STATUSES = frozenset({"ok", "failing", "unknown"})

NOT_VISIBLE = [
    {
        "what": "Per-group environment variables",
        "why": "ncl leaves env out of a group's config, and the console never reads NanoClaw's "
        "database or .env.",
    },
    {
        "what": "OneCLI secret assignments",
        "why": "They live in OneCLI's vault; the console has no access to OneCLI.",
    },
    {
        "what": "Egress lockdown",
        "why": "It is an environment setting of NanoClaw's and a Docker network; the broker has "
        "neither the Docker socket nor .env.",
    },
]


# -- reading ------------------------------------------------------------------------------------


@dataclass
class Context:
    """One request's reads: the clients, the time, and what failed."""

    broker: BrokerClient
    loki: LokiClient | None
    cache: TtlCache
    timezone: ZoneInfo
    now: datetime
    broker_errors: dict[str, str] = field(default_factory=dict)
    loki_errors: dict[str, str] = field(default_factory=dict)

    async def read(self, verb: str, params: Mapping[str, str] | None = None) -> object:
        """The verb's data, or None with the failure recorded."""
        try:
            return await self.broker.call(verb, params)
        except BrokerError as exc:
            self.broker_errors[verb] = exc.code
            return None

    async def _loki[T](self, name: str, load: Callable[[LokiClient], Awaitable[T]]) -> T | None:
        loki = self.loki
        if loki is None:
            self.loki_errors[name] = "not_configured"
            return None
        try:
            return await self.cache.get(name, lambda: load(loki))
        except LokiError as exc:
            self.loki_errors[name] = exc.code
            return None

    async def claude_signals(self) -> ClaudeSignals | None:
        return await self._loki("claude", lambda loki: read_signals(loki, self.now))

    async def host_logs(self) -> HostLogs | None:
        return await self._loki("host_logs", lambda loki: read_host_logs(loki, self.now))

    def sources(self, *, loki: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "broker": {"ok": not self.broker_errors, "errors": dict(self.broker_errors)}
        }
        if loki:
            out["loki"] = {"ok": not self.loki_errors, "errors": dict(self.loki_errors)}
        return out


# -- small readers ------------------------------------------------------------------------------


def _rows(data: object) -> list[dict[str, Any]]:
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def _time(value: object) -> str | None:
    return iso(parse_time(value))


def _count(data: object) -> int | None:
    return len(data) if isinstance(data, list) else None


def _group_index(groups: object) -> dict[str, dict[str, Any]]:
    return {
        g["id"]: {"id": g["id"], "name": _str(g.get("name")), "folder": _str(g.get("folder"))}
        for g in _rows(groups)
        if isinstance(g.get("id"), str)
    }


def _group_ref(group_id: object, index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(group_id, str):
        return None
    return {"id": group_id, "name": index.get(group_id, {}).get("name")}


# -- tasks --------------------------------------------------------------------------------------


def task_item(
    row: Mapping[str, Any],
    groups: Mapping[str, Mapping[str, Any]],
    tz: ZoneInfo,
    now: datetime,
) -> dict[str, Any]:
    series = _str(row.get("series_id")) or _str(row.get("row_id")) or ""
    status = _str(row.get("status"))
    process_after = parse_time(row.get("process_after"))
    started = series_started_at(series, now)
    group_id = _str(row.get("agent_group_id"))
    group = groups.get(group_id or "", {})
    recurrence = row.get("recurrence") if "recurrence" in row else row.get("schedule")
    return {
        "id": series,
        "row_id": _str(row.get("row_id")),
        "group": {"id": group_id, "name": group.get("name"), "folder": group.get("folder")},
        "status": status,
        "overdue_on_resume": overdue_on_resume(status, process_after, now),
        "prompt": _str(row.get("prompt")),
        "task_file": task_file_name(row.get("prompt")),
        "has_script": bool(row.get("has_script")),
        "schedule": describe_schedule(_str(recurrence), tz, now),
        "next_run_at": None if status in _NOT_SCHEDULED else iso(process_after),
        "process_after": iso(process_after),
        "last_run_at": _time(row.get("last_run")),
        "runs": _int(row.get("runs")),
        "failed_runs": _int(row.get("failed_runs")),
        "tries": _int(row.get("tries")),
        "series_started_at": iso(started),
        "series_age_days": (now - started).days if started is not None else None,
        "occurrence_created_at": _time(row.get("created_at")),
        "session_id": _str(row.get("session_id")),
    }


def _sort_tasks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda t: (t["next_run_at"] is None, t["next_run_at"] or "", t["id"]))


def _task_items(ctx: Context, tasks: object, groups: object) -> list[dict[str, Any]]:
    index = _group_index(groups)
    return _sort_tasks([task_item(r, index, ctx.timezone, ctx.now) for r in _rows(tasks)])


async def tasks_view(ctx: Context) -> dict[str, Any]:
    tasks, groups = await asyncio.gather(ctx.read("tasks-list"), ctx.read("groups-list"))
    return {
        "generated_at": iso(ctx.now),
        "timezone": ctx.timezone.key,
        "tasks": _task_items(ctx, tasks, groups),
        "sources": ctx.sources(loki=False),
    }


class NotFound(Exception):
    pass


class Unavailable(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _task_file(data: object) -> dict[str, Any] | None:
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        return None
    return {
        "name": _str(data.get("name")),
        "content": data["content"],
        "truncated": bool(data.get("truncated")),
    }


async def task_detail(ctx: Context, series_id: str) -> dict[str, Any]:
    """One task; raises `NotFound` or `Unavailable` when no partial answer is possible."""
    params = {"id": series_id}

    async def get() -> tuple[Any, BrokerError | None]:
        try:
            return await ctx.broker.call("tasks-get", params), None
        except BrokerError as exc:
            return None, exc

    (got, got_error), tasks, groups, file_data = await asyncio.gather(
        get(), ctx.read("tasks-list"), ctx.read("groups-list"), ctx.read("task-file", params)
    )
    index = _group_index(groups)
    listed = next((r for r in _rows(tasks) if r.get("series_id") == series_id), None)
    if got_error is not None:
        if listed is None:  # nothing to show: unknown to ncl, or the broker cannot say
            raise NotFound if got_error.code == "ncl_error" else Unavailable(got_error.code)
        ctx.broker_errors["tasks-get"] = got_error.code
    detail = got if isinstance(got, dict) else {}
    if listed is not None:
        task = task_item(listed, index, ctx.timezone, ctx.now)
    else:
        task = task_item(
            {**detail, "runs": detail.get("completed_runs")}, index, ctx.timezone, ctx.now
        )
    if isinstance(detail.get("prompt"), str):
        task["prompt"] = detail["prompt"]
        task["task_file"] = task_file_name(detail["prompt"])
    log = detail.get("recent_log")
    task["recent_log"] = [str(line) for line in log] if isinstance(log, list) else []
    task["completed_runs"] = _int(detail.get("completed_runs"))
    return {
        "generated_at": iso(ctx.now),
        "timezone": ctx.timezone.key,
        "task": task,
        "task_file": _task_file(file_data),
        "sources": ctx.sources(loki=False),
    }


# -- groups -------------------------------------------------------------------------------------


def _mcp_servers(servers: object) -> list[dict[str, Any]]:
    if not isinstance(servers, dict):
        return []
    out = []
    for name in sorted(servers):
        entry = servers[name] if isinstance(servers[name], dict) else {}
        headers = entry.get("headers")
        env = entry.get("env")
        args = entry.get("args")
        out.append(
            {
                "name": str(name),
                "type": _str(entry.get("type")),
                "transport": _str(entry.get("transport")),
                "url": _str(entry.get("url")),
                "command": _str(entry.get("command")),
                "header_names": sorted(str(k) for k in headers)
                if isinstance(headers, dict)
                else [],
                "env_names": sorted(str(k) for k in env) if isinstance(env, dict) else [],
                "arg_count": len(args) if isinstance(args, list) else 0,
            }
        )
    return out


def _mounts(mounts: object) -> list[dict[str, Any]]:
    return [
        {
            "host_path": _str(m.get("hostPath")),
            "container_path": _str(m.get("containerPath")),
            "read_only": bool(m.get("readonly")),
        }
        for m in _rows(mounts)
    ]


_CONFIG_FIELDS = (
    "model",
    "provider",
    "effort",
    "speed",
    "assistant_name",
    "cli_scope",
    "timezone",
    "image_tag",
    "max_messages_per_prompt",
    "skills",
)


def _config(config: object) -> dict[str, Any] | None:
    if not isinstance(config, dict):
        return None
    out: dict[str, Any] = {}
    for key in _CONFIG_FIELDS:
        value = config.get(key)
        out[key] = value if isinstance(value, str | int | float | bool) or value is None else None
    for key in ("packages_apt", "packages_npm"):
        value = config.get(key)
        out[key] = [str(v) for v in value] if isinstance(value, list) else []
    out["updated_at"] = _time(config.get("updated_at"))
    out["mcp_servers"] = _mcp_servers(config.get("mcp_servers"))
    out["mounts"] = _mounts(config.get("additional_mounts"))
    return out


def _channel(wiring: Mapping[str, Any], mg: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "wiring_id": _str(wiring.get("id")),
        "messaging_group_id": _str(wiring.get("messaging_group_id")),
        "name": _str(mg.get("name")),
        "channel_type": _str(mg.get("channel_type")),
        "instance": _str(mg.get("instance")),
        "platform_id": _str(mg.get("platform_id")),
        "is_group": _bool(mg.get("is_group")),
        "engage_mode": _str(wiring.get("engage_mode")),
        "engage_pattern": _str(wiring.get("engage_pattern")),
        "sender_scope": _str(wiring.get("sender_scope")),
        "ignored_message_policy": _str(wiring.get("ignored_message_policy")),
        "unknown_sender_policy": _str(mg.get("unknown_sender_policy")),
        "session_mode": _str(wiring.get("session_mode")),
        "priority": _int(wiring.get("priority")),
        "threads": wiring.get("threads") if isinstance(wiring.get("threads"), str | int) else None,
        "denied_at": _time(mg.get("denied_at")),
    }


def _destination(
    row: Mapping[str, Any],
    mgs: Mapping[str, Mapping[str, Any]],
    groups: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    target = _str(row.get("target_id")) or ""
    target_name = _str(mgs.get(target, {}).get("name")) or groups.get(target, {}).get("name")
    return {
        "local_name": _str(row.get("local_name")),
        "display_name": _str(row.get("display_name")),
        "channel_type": _str(row.get("channel_type")),
        "target_type": _str(row.get("target_type")),
        "target_id": target or None,
        "target_name": target_name,
        "created_at": _time(row.get("created_at")),
    }


def _unwired(mg: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _str(mg.get("id")),
        "name": _str(mg.get("name")),
        "channel_type": _str(mg.get("channel_type")),
        "instance": _str(mg.get("instance")),
        "platform_id": _str(mg.get("platform_id")),
        "unknown_sender_policy": _str(mg.get("unknown_sender_policy")),
        "denied_at": _time(mg.get("denied_at")),
    }


async def groups_view(ctx: Context) -> dict[str, Any]:
    groups, wirings, mgs, dests, sessions, tasks = await asyncio.gather(
        ctx.read("groups-list"),
        ctx.read("wirings-list"),
        ctx.read("messaging-groups-list"),
        ctx.read("destinations-list"),
        ctx.read("sessions-list"),
        ctx.read("tasks-list"),
    )
    group_rows = [g for g in _rows(groups) if isinstance(g.get("id"), str)]
    configs = await asyncio.gather(
        *(ctx.read("groups-config-get", {"id": g["id"]}) for g in group_rows)
    )
    index = _group_index(groups)
    mg_index = {m["id"]: m for m in _rows(mgs) if isinstance(m.get("id"), str)}
    task_items = _task_items(ctx, tasks, groups)
    wired = {str(w.get("messaging_group_id")) for w in _rows(wirings)}
    out = []
    for group, config in zip(group_rows, configs, strict=True):
        gid = group["id"]
        mine = [w for w in _rows(wirings) if w.get("agent_group_id") == gid]
        group_sessions = [s for s in _rows(sessions) if s.get("agent_group_id") == gid]
        group_tasks = [t for t in task_items if t["group"]["id"] == gid]
        out.append(
            {
                "id": gid,
                "name": _str(group.get("name")),
                "folder": _str(group.get("folder")),
                "created_at": _time(group.get("created_at")),
                "config": _config(config),
                "channels": [
                    _channel(w, mg_index.get(str(w.get("messaging_group_id")), {})) for w in mine
                ],
                "destinations": [
                    _destination(d, mg_index, index)
                    for d in _rows(dests)
                    if d.get("agent_group_id") == gid
                ],
                "sessions": {
                    "total": len(group_sessions),
                    "running": sum(
                        1 for s in group_sessions if s.get("container_status") == "running"
                    ),
                },
                "tasks": {
                    "total": len(group_tasks),
                    "paused": sum(1 for t in group_tasks if t["status"] == "paused"),
                    "overdue_on_resume": sum(1 for t in group_tasks if t["overdue_on_resume"]),
                },
            }
        )
    return {
        "generated_at": iso(ctx.now),
        "groups": out,
        "unwired_channels": [_unwired(m) for mid, m in mg_index.items() if mid not in wired],
        "sources": ctx.sources(loki=False),
    }


# -- permissions --------------------------------------------------------------------------------


def _users(users: object) -> dict[str, Mapping[str, Any]]:
    return {u["id"]: u for u in _rows(users) if isinstance(u.get("id"), str)}


def _approval(
    row: Mapping[str, Any], groups: Mapping[str, Mapping[str, Any]], now: datetime
) -> dict[str, Any]:
    created = parse_time(row.get("created_at"))
    status = _str(row.get("status"))
    return {
        "id": _str(row.get("approval_id")) or _str(row.get("request_id")),
        "action": _str(row.get("action")),
        "title": _str(row.get("title")),
        "status": status,
        "created_at": iso(created),
        "expires_at": _time(row.get("expires_at")),
        "age_days": (now - created).days if created is not None else None,
        "stale": status == "pending" and created is not None and now - created > STALE_APPROVAL,
        "group": _group_ref(row.get("agent_group_id"), groups),
        "session_id": _str(row.get("session_id")),
    }


def _mount_allowlist(data: object, failed: bool) -> dict[str, Any]:
    if failed:
        return {"available": False, "reason": "broker_error"}
    if not isinstance(data, dict) or data.get("available") is False:
        return {"available": False, "reason": "not_readable"}
    patterns = data.get("blockedPatterns")
    return {
        "available": True,
        "allowed_roots": [
            {
                "path": _str(r.get("path")),
                "read_write": r.get("allowReadWrite") is True,
                "description": _str(r.get("description")),
            }
            for r in _rows(data.get("allowedRoots"))
        ],
        "blocked_patterns": [str(p) for p in patterns] if isinstance(patterns, list) else [],
        "non_main_read_only": _bool(data.get("nonMainReadOnly")),
    }


async def permissions_view(ctx: Context) -> dict[str, Any]:
    (
        roles,
        members,
        policies,
        dests,
        approvals,
        users,
        groups,
        mgs,
        allowlist,
    ) = await asyncio.gather(
        ctx.read("roles-list"),
        ctx.read("members-list"),
        ctx.read("policies-list"),
        ctx.read("destinations-list"),
        ctx.read("approvals-list"),
        ctx.read("users-list"),
        ctx.read("groups-list"),
        ctx.read("messaging-groups-list"),
        ctx.read("mount-allowlist"),
    )
    index = _group_index(groups)
    people = _users(users)
    mg_index = {m["id"]: m for m in _rows(mgs) if isinstance(m.get("id"), str)}

    def person(user_id: object) -> dict[str, Any]:
        user = people.get(user_id) if isinstance(user_id, str) else None
        return {
            "user_id": _str(user_id),
            "user_name": _str(user.get("display_name")) if user else None,
            "user_kind": _str(user.get("kind")) if user else None,
        }

    return {
        "generated_at": iso(ctx.now),
        "roles": [
            {
                **person(r.get("user_id")),
                "role": _str(r.get("role")),
                "scope": "global" if r.get("agent_group_id") is None else "group",
                "group": _group_ref(r.get("agent_group_id"), index),
                "granted_at": _time(r.get("granted_at")),
                "granted_by": _str(r.get("granted_by")),
            }
            for r in _rows(roles)
        ],
        "members": [
            {
                **person(m.get("user_id")),
                "group": _group_ref(m.get("agent_group_id"), index),
                "added_at": _time(m.get("added_at")),
                "added_by": _str(m.get("added_by")),
            }
            for m in _rows(members)
        ],
        "policies": _rows(policies),
        "destinations": [
            {
                "group": _group_ref(d.get("agent_group_id"), index),
                **_destination(d, mg_index, index),
            }
            for d in _rows(dests)
        ],
        "mount_allowlist": _mount_allowlist(allowlist, "mount-allowlist" in ctx.broker_errors),
        "approvals": [_approval(a, index, ctx.now) for a in _rows(approvals)],
        "not_visible": NOT_VISIBLE,
        "sources": ctx.sources(loki=False),
    }


# -- Claude, health and quota -------------------------------------------------------------------


def _probe(data: object) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    return {
        "status": status if status in _PROBE_STATUSES else "unknown",
        "http_status": _int(data.get("http_status")),
        "checked_at": _time(data.get("checked_at")),
    }


def claude_block(signals: ClaudeSignals | None, probe: dict[str, Any] | None) -> dict[str, Any]:
    status, reasons = claude_status(signals, probe)
    call = signals.last_agent_call if signals else None
    return {
        "status": status,
        "reasons": reasons,
        "last_agent_call": None
        if call is None
        else {
            "at": iso(call.at),
            "status": call.status,
            "agent": call.agent,
            "injections_applied": call.injections_applied,
        },
        "last_success_at": iso(signals.last_success_at) if signals else None,
        "agent_calls_24h": signals.agent_calls_24h if signals else None,
        "auth_failures_1h": signals.auth_failures_1h if signals else None,
        "auth_failures_24h": signals.auth_failures_24h if signals else None,
        "probe": probe,
    }


def nanoclaw_block(health: object, failed: bool) -> dict[str, Any]:
    if failed:
        return {"available": False, "reason": "broker_error"}
    if not isinstance(health, dict) or health.get("available") is False:
        return {"available": False, "reason": "not_answering"}
    queue = _dict(health.get("queue"))
    tasks = _dict(health.get("tasks"))
    return {
        "available": True,
        "healthy": _bool(health.get("healthy")),
        "uptime_seconds": _int(health.get("uptimeSeconds")),
        "message_loop_running": _bool(health.get("messageLoopRunning")),
        "channels": [
            {"name": _str(c.get("name")), "connected": _bool(c.get("connected"))}
            for c in _rows(health.get("channels"))
        ],
        "queue": {k: _int(queue.get(k)) for k in ("active", "max", "waiting")},
        "registered_group_count": _int(health.get("registeredGroupCount")),
        "active_session_count": _int(health.get("activeSessionCount")),
        "last_message_at": _time(health.get("lastMessageTimestamp")),
        "tasks": {
            "active_count": _int(tasks.get("activeCount")),
            "paused_count": _int(tasks.get("pausedCount")),
            "next_run_at": _time(tasks.get("nextRunTime")),
            "recent_failures": _int(tasks.get("recentFailures")),
        },
    }


def quota_block(usage: object, failed: bool) -> dict[str, Any]:
    """D6, F7: always the host login's quota, labelled so, never NanoClaw's token."""
    if failed or not isinstance(usage, dict):
        return {"available": False, "reason": "broker_error", "label": QUOTA_LABEL}
    pct = usage.get("weekly_pct")
    return {
        "available": True,
        "label": QUOTA_LABEL,
        "source": QUOTA_SOURCE,
        "weekly_pct": pct if isinstance(pct, int | float) and not isinstance(pct, bool) else None,
        "resets_at": _time(usage.get("resets_at")),
        "resets_text": _str(usage.get("resets_text")),
    }


# -- problems -----------------------------------------------------------------------------------


def _item(
    kind: str,
    severity: str,
    title: str,
    *,
    detail: str | None = None,
    at: str | None = None,
    count: int | None = None,
    ref: tuple[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": detail,
        "at": at,
        "count": count,
        "ref": {"type": ref[0], "id": ref[1]} if ref else None,
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _source_items(ctx: Context, *, loki: bool) -> list[dict[str, Any]]:
    items = []
    if ctx.broker_errors:
        failed = ", ".join(f"{v} ({c})" for v, c in sorted(ctx.broker_errors.items()))
        items.append(
            _item(
                "source_unavailable",
                "error",
                "The broker did not answer every read",
                detail=f"Failed: {failed}.",
                ref=("source", "broker"),
            )
        )
    if loki and ctx.loki_errors:
        if set(ctx.loki_errors.values()) == {"not_configured"}:
            title = "Loki is not configured (LOKI_URL is unset)"
        else:
            title = "Loki did not answer"
        failed = ", ".join(f"{v} ({c})" for v, c in sorted(ctx.loki_errors.items()))
        items.append(
            _item(
                "source_unavailable",
                "error",
                title,
                detail=f"Failed: {failed}.",
                ref=("source", "loki"),
            )
        )
    return items


def _claude_items(claude: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = []
    detail = " ".join(claude["reasons"])
    if claude["status"] == "failing":
        items.append(_item("claude_failing", "error", "Claude is failing", detail=detail))
    elif claude["status"] == "degraded":
        items.append(_item("claude_degraded", "warning", "Claude is degraded", detail=detail))
    elif claude["status"] == "unknown":
        items.append(_item("claude_unknown", "info", "Claude's health is unknown", detail=detail))
    failures = claude["auth_failures_24h"] or 0
    if failures:
        recent = claude["auth_failures_1h"] or 0
        items.append(
            _item(
                "claude_auth_failures",
                "error" if recent else "warning",
                f"{_plural(failures, 'call')} to Claude refused (401 or 403) in 24 hours",
                detail=f"{recent} in the last hour.",
                count=failures,
            )
        )
    return items


def _health_items(nanoclaw: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not nanoclaw["available"]:
        if nanoclaw["reason"] == "not_answering":
            return [
                _item(
                    "nanoclaw_not_answering", "error", "NanoClaw's health endpoint did not answer"
                )
            ]
        return []
    items = []
    if nanoclaw["healthy"] is False:
        items.append(_item("nanoclaw_unhealthy", "error", "NanoClaw reports itself unhealthy"))
    for channel in nanoclaw["channels"]:
        if channel["connected"] is False:
            items.append(
                _item(
                    "channel_disconnected",
                    "error",
                    f"Channel {channel['name']} is not connected",
                    ref=("channel", str(channel["name"])),
                )
            )
    if nanoclaw["message_loop_running"] is False:
        items.append(
            _item("message_loop_stopped", "error", "NanoClaw's message loop is not running")
        )
    return items


def _log_items(logs: HostLogs | None) -> list[dict[str, Any]]:
    if logs is None:
        return []
    items = []
    for level, total, kind, severity, word in (
        ("ERROR", logs.errors, "host_log_errors", "error", "error"),
        ("WARN", logs.warnings, "host_log_warnings", "warning", "warning"),
    ):
        groups = [g for g in logs.groups if g.level == level]
        if not total or not groups:
            continue
        top = max(groups, key=lambda g: g.count)
        items.append(
            _item(
                kind,
                severity,
                f"NanoClaw logged {_plural(total, word)} in 24 hours",
                detail=f"Most frequent: {top.message} ({top.count}).",
                at=iso(max(g.last_at for g in groups)),
                count=total,
            )
        )
    return items


def _task_items_problems(tasks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for task in tasks:
        label = task["task_file"] or task["id"]
        if task["overdue_on_resume"]:
            words = task["schedule"]["words"]
            then = f"then {_lower_first(words)}" if words else "then on its schedule"
            items.append(
                _item(
                    "task_paused_overdue",
                    "warning",
                    f"{label} is paused and overdue",
                    detail=f"Resuming it runs it once straight away, {then}.",
                    at=task["process_after"],
                    ref=("task", task["id"]),
                )
            )
        failed = task["failed_runs"] or 0
        if failed:
            items.append(
                _item(
                    "task_failures",
                    "warning",
                    f"{label} has {_plural(failed, 'failed run')}",
                    at=task["last_run_at"],
                    count=failed,
                    ref=("task", task["id"]),
                )
            )
    return items


def _approval_items(approvals: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _item(
            "approval_stale",
            "warning",
            f"An approval has waited {a['age_days']} days",
            detail=f"{a['title'] or 'Untitled'} ({a['action'] or 'unknown action'}).",
            at=a["created_at"],
            ref=("approval", str(a["id"])),
        )
        for a in approvals
        if a["stale"]
    ]


def _dropped_items(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        count = _int(row.get("message_count")) or 0
        reason = (_str(row.get("reason")) or "unknown reason").replace("_", " ")
        items.append(
            _item(
                "dropped_messages",
                "info",
                f"{_plural(count, 'message')} dropped: {reason}",
                detail=f"Channel {row.get('messaging_group_id')} "
                f"({_str(row.get('channel_type')) or 'unknown type'}).",
                at=_time(row.get("last_seen")),
                count=count,
                ref=("channel", str(row.get("messaging_group_id"))),
            )
        )
    return items


def _sorted_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda i: (
            _SEVERITY[i["severity"]],
            i["at"] is not None,
            # newest first: invert the ISO string order through a negated timestamp
            -(parse_time(i["at"]).timestamp()) if i["at"] else 0.0,  # type: ignore[union-attr]
        ),
    )


@dataclass
class _Snapshot:
    """Everything the overview and the problems view both read."""

    claude: dict[str, Any]
    nanoclaw: dict[str, Any]
    quota: dict[str, Any]
    tasks: list[dict[str, Any]]
    approvals: list[dict[str, Any]]
    raw: dict[str, object]
    logs: HostLogs | None


async def _snapshot(ctx: Context) -> _Snapshot:
    names = (
        "health",
        "usage",
        "claude-probe",
        "tasks-list",
        "groups-list",
        "approvals-list",
        "dropped-messages-list",
        "messaging-groups-list",
        "wirings-list",
        "sessions-list",
    )

    async def broker_reads() -> dict[str, object]:
        values = await asyncio.gather(*(ctx.read(n) for n in names))
        return dict(zip(names, values, strict=True))

    raw, signals, logs = await asyncio.gather(broker_reads(), ctx.claude_signals(), ctx.host_logs())
    index = _group_index(raw["groups-list"])
    return _Snapshot(
        claude=claude_block(signals, _probe(raw["claude-probe"])),
        nanoclaw=nanoclaw_block(raw["health"], "health" in ctx.broker_errors),
        quota=quota_block(raw["usage"], "usage" in ctx.broker_errors),
        tasks=_task_items(ctx, raw["tasks-list"], raw["groups-list"]),
        approvals=[_approval(a, index, ctx.now) for a in _rows(raw["approvals-list"])],
        raw=raw,
        logs=logs,
    )


def _problems(ctx: Context, snap: _Snapshot) -> list[dict[str, Any]]:
    return _sorted_items(
        _source_items(ctx, loki=True)
        + _claude_items(snap.claude)
        + _health_items(snap.nanoclaw)
        + _log_items(snap.logs)
        + _task_items_problems(snap.tasks)
        + _approval_items(snap.approvals)
        + _dropped_items(_rows(snap.raw["dropped-messages-list"]))
    )


def _host_logs_block(logs: HostLogs | None) -> dict[str, Any] | None:
    if logs is None:
        return None
    return {
        "window_hours": WINDOW_HOURS,
        "errors": logs.errors,
        "warnings": logs.warnings,
        "truncated": logs.truncated,
        "groups": [
            {
                "level": g.level,
                "message": g.message,
                "count": g.count,
                "first_at": iso(g.first_at),
                "last_at": iso(g.last_at),
                "sample": g.sample,
            }
            for g in logs.groups
        ],
    }


async def problems_view(ctx: Context) -> dict[str, Any]:
    snap = await _snapshot(ctx)
    return {
        "generated_at": iso(ctx.now),
        "items": _problems(ctx, snap),
        "host_logs": _host_logs_block(snap.logs),
        "sources": ctx.sources(loki=True),
    }


async def overview_view(ctx: Context) -> dict[str, Any]:
    snap = await _snapshot(ctx)
    raw = snap.raw
    tasks_read = "tasks-list" not in ctx.broker_errors
    approvals_read = "approvals-list" not in ctx.broker_errors
    return {
        "generated_at": iso(ctx.now),
        "claude": snap.claude,
        "nanoclaw": snap.nanoclaw,
        "quota": snap.quota,
        "counts": {
            "groups": _count(raw["groups-list"]),
            "channels": _count(raw["messaging-groups-list"]),
            "wirings": _count(raw["wirings-list"]),
            "sessions": _count(raw["sessions-list"]),
            "tasks": len(snap.tasks) if tasks_read else None,
            "tasks_paused": sum(1 for t in snap.tasks if t["status"] == "paused")
            if tasks_read
            else None,
            "tasks_overdue_on_resume": sum(1 for t in snap.tasks if t["overdue_on_resume"])
            if tasks_read
            else None,
            "pending_approvals": sum(1 for a in snap.approvals if a["status"] == "pending")
            if approvals_read
            else None,
            "dropped_messages": _count(raw["dropped-messages-list"]),
            "host_errors_24h": snap.logs.errors if snap.logs else None,
            "host_warnings_24h": snap.logs.warnings if snap.logs else None,
        },
        "warnings": _problems(ctx, snap),
        "sources": ctx.sources(loki=True),
    }
