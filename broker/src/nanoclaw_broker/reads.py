"""The reads that are not an ncl command (docs/architecture.md §3.8).

`LocalReads.run` is called by the server for a `LocalVerb`. Its answers are the shapes the console
is built against:

    health           the /health JSON as is, or {"available": false}
    mount-allowlist  the allowlist file as is, or {"available": false}
    task-file        {name, content, truncated} or {"file": null}
    claude-probe     {status, http_status, checked_at}
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from .events import EventLog
from .health import fetch_health
from .probe import ClaudeProbe
from .redact import redact_document, redact_reply
from .safefs import Refused, read_below
from .verbs import ID_PATTERN, REGISTRY, Verb

# Every live task prompt starts like this; /workspace/agent is groups/<folder>/ (plan W5).
_TASK_FILE = re.compile(r"Read /workspace/agent/tasks/([A-Za-z0-9._-]{1,80}\.md)\b")
_UNAVAILABLE: dict[str, object] = {"available": False}

# Broker._fetch: a cached, capped ncl call. Returns (data, how it was served).
NclFetch = Callable[[Verb, dict[str, str]], Awaitable[tuple[object, str]]]


class LocalReads:
    def __init__(
        self,
        *,
        groups_dir: Path,
        mount_allowlist: Path,
        health_port: int,
        probe: ClaudeProbe,
        ncl: NclFetch,
        events: EventLog,
    ) -> None:
        self._groups_dir = groups_dir
        self._mount_allowlist = mount_allowlist
        self._health_port = health_port
        self._probe = probe
        self._ncl = ncl
        self._events = events
        self._handlers: dict[str, Callable[[dict[str, str]], Awaitable[object]]] = {
            "health": self._health,
            "mount-allowlist": self._mounts,
            "task-file": self._task_file,
            "claude-probe": self._claude_probe,
        }

    async def run(self, name: str, params: dict[str, str]) -> object:
        return await self._handlers[name](params)

    async def _health(self, params: dict[str, str]) -> object:
        return await fetch_health(self._health_port)

    async def _claude_probe(self, params: dict[str, str]) -> object:
        return await self._probe.run()

    async def _mounts(self, params: dict[str, str]) -> object:
        path = self._mount_allowlist
        try:
            raw, truncated = await asyncio.to_thread(read_below, path.parent, (path.name,))
            data = json.loads(raw)
        except Refused as exc:
            self._events.emit("mount_allowlist_refused", reason=exc.reason)
            return dict(_UNAVAILABLE)
        except ValueError:  # not UTF-8, or not JSON
            return dict(_UNAVAILABLE)
        if truncated or not isinstance(data, dict):
            return dict(_UNAVAILABLE)
        return redact_reply(data)

    async def _task_file(self, params: dict[str, str]) -> object:
        series = params["id"]
        task, _ = await self._ncl(REGISTRY["tasks-get"], {"id": series})
        name, group_id = _task_file_name(task)
        if name is None or group_id is None:
            return {"file": None}
        group, _ = await self._ncl(REGISTRY["groups-get"], {"id": group_id})
        folder = group.get("folder") if isinstance(group, dict) else None
        try:
            if not isinstance(folder, str):
                raise Refused("bad_path")
            raw, truncated = await asyncio.to_thread(
                read_below, self._groups_dir, (folder, "tasks", name)
            )
        except Refused as exc:
            self._events.emit("task_file_refused", id=series, reason=exc.reason)
            return {"file": None}
        text = raw.decode("utf-8", errors="replace")
        return {"name": name, "content": redact_document(text), "truncated": truncated}


def _task_file_name(task: object) -> tuple[str | None, str | None]:
    """The task file its prompt names, and the agent group to find it under."""
    if not isinstance(task, dict):
        return None, None
    prompt = task.get("prompt")
    group_id = task.get("agent_group_id")
    if not isinstance(prompt, str) or not isinstance(group_id, str):
        return None, None
    match = _TASK_FILE.match(prompt)
    if match is None or ID_PATTERN.fullmatch(group_id) is None:
        return None, None
    return match.group(1), group_id
