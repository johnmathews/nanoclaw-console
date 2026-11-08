"""Redaction of ncl replies (docs/architecture.md §3.5).

Runs on `data` inside the cache loader, before anything is cached, logged or returned. The rules
apply wherever a key appears, so a field that moves or appears in another verb's reply upstream is
still covered. Functions here never mutate their input.
"""

import re
from urllib.parse import urlsplit

MASK = "•••"

# The keys NanoClaw 479a9510's presentConfig returns (src/cli/resources/groups.ts:74-94). Anything
# else in a `groups-config-get` reply (an `env` block, a field added upstream) is dropped.
GROUP_CONFIG_KEYS = frozenset(
    {
        "agent_group_id",
        "provider",
        "model",
        "effort",
        "speed",
        "image_tag",
        "assistant_name",
        "max_messages_per_prompt",
        "skills",
        "mcp_servers",
        "packages_apt",
        "packages_npm",
        "additional_mounts",
        "cli_scope",
        "timezone",
        "updated_at",
    }
)

_MASKED_OBJECTS = frozenset({"headers", "env"})
_DROPPED = frozenset({"payload"})
_USERINFO = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/?#@]+@")
_PLAIN_COMMAND = re.compile(r"[A-Za-z0-9_./-]{1,200}")
_PLAIN_WORD = re.compile(r"[A-Za-z0-9_-]{1,40}")


def reduce_url(value: object) -> str:
    """`scheme://host[:port]`; userinfo, path, query and fragment go. Anything else: MASK."""
    if not isinstance(value, str):
        return MASK
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return MASK
    host = parts.hostname
    if not parts.scheme or not host:
        return MASK
    if ":" in host:
        host = f"[{host}]"
    return f"{parts.scheme.lower()}://{host}" + (f":{port}" if port is not None else "")


def strip_userinfo(text: str) -> str:
    """Replace the `user[:password]` of every `scheme://user[:password]@` with MASK."""
    return _USERINFO.sub(rf"\g<1>{MASK}@", text)


def redact_reply(data: object) -> object:
    """The rules every verb's reply goes through."""
    if isinstance(data, dict):
        return _redact_object(data)
    if isinstance(data, list):
        return [redact_reply(item) for item in data]
    if isinstance(data, str):
        return strip_userinfo(data)
    return data


def redact_group_config(data: object) -> object:
    """`groups-config-get`: only presentConfig's known keys, then the common rules."""
    if not isinstance(data, dict):
        return MASK
    return redact_reply({k: v for k, v in data.items() if k in GROUP_CONFIG_KEYS})


def _redact_object(obj: dict[object, object]) -> dict[object, object]:
    out: dict[object, object] = {}
    for key, value in obj.items():
        if key in _DROPPED or key in ("script", "has_script"):
            continue
        if key in _MASKED_OBJECTS:
            out[key] = _mask_values(value)
        elif key == "mcp_servers":
            out[key] = _redact_mcp_servers(value)
        elif isinstance(key, str) and (key == "url" or key.endswith("_url")):
            out[key] = reduce_url(value)
        else:
            out[key] = redact_reply(value)
    if "script" in obj or "has_script" in obj:
        out["has_script"] = bool(obj.get("script")) or _is_set(obj.get("has_script"))
    return out


def _is_set(flag: object) -> bool:
    """ncl's `has_script` is 0 or 1; only a real 1 or true counts (not the string "1")."""
    return flag is True or (type(flag) is int and flag == 1)


def _mask_values(value: object) -> object:
    if isinstance(value, dict):
        return dict.fromkeys(value, MASK)
    return MASK


def _redact_mcp_servers(value: object) -> object:
    if not isinstance(value, dict):
        return MASK
    return {name: _redact_mcp_entry(entry) for name, entry in value.items()}


def _redact_mcp_entry(entry: object) -> object:
    """Keep what the UI needs (kind, host, which headers and variables exist); mask the rest."""
    if not isinstance(entry, dict):
        return MASK
    out: dict[object, object] = {}
    for key, value in entry.items():
        if key in ("type", "transport"):
            out[key] = _keep_if(value, _PLAIN_WORD)
        elif key == "url":
            out[key] = reduce_url(value)
        elif key in _MASKED_OBJECTS:
            out[key] = _mask_values(value)
        elif key == "command":
            out[key] = _keep_if(value, _PLAIN_COMMAND)
        elif key == "args":
            out[key] = [MASK] * len(value) if isinstance(value, list) else MASK
        else:
            out[key] = MASK
    return out


def _keep_if(value: object, pattern: re.Pattern[str]) -> object:
    if isinstance(value, str) and pattern.fullmatch(value):
        return value
    return MASK
