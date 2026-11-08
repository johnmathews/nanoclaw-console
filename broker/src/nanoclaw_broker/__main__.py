"""Entry point: `python -m nanoclaw_broker`.

Options: `--socket`, `--ncl-socket`, `--socket-mode`, `--socket-group`, and for the extra reads
`--groups-dir`, `--mount-allowlist`, `--health-port`, `--onecli-url`, `--probe-agent-group`.
Serves the console until SIGTERM or SIGINT, then removes its socket and exits 0
(docs/architecture.md §3.7).
"""

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit

from .server import (
    DEFAULT_GROUPS_DIR,
    DEFAULT_HEALTH_PORT,
    DEFAULT_MOUNT_ALLOWLIST,
    DEFAULT_ONECLI_URL,
    DEFAULT_PROBE_AGENT_GROUP,
    BrokerConfig,
    serve,
)
from .verbs import ID_PATTERN

DEFAULT_SOCKET = "/run/nanoclaw-console/broker.sock"
DEFAULT_NCL_SOCKET = "/srv/apps/nanoclaw/data/ncl.sock"


def _mode(text: str) -> int:
    """An octal permission mode such as 0660; no setuid, setgid or sticky bits."""
    if not text or len(text) > 4 or any(c not in "01234567" for c in text):
        raise argparse.ArgumentTypeError(f"not an octal mode: {text!r}")
    value = int(text, 8)
    if value > 0o777:
        raise argparse.ArgumentTypeError(f"mode out of range (0-0777): {text!r}")
    return value


def _gid(text: str) -> int:
    if not text.isdigit():
        raise argparse.ArgumentTypeError(f"not a numeric gid: {text!r}")
    return int(text)


def _port(text: str) -> int:
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise argparse.ArgumentTypeError(f"not a port (1-65535): {text!r}")
    return int(text)


def _agent_group(text: str) -> str:
    if ID_PATTERN.fullmatch(text) is None:
        raise argparse.ArgumentTypeError(f"not an agent group id: {text!r}")
    return text


def _http_url(text: str) -> str:
    try:
        parts = urlsplit(text)
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an http URL: {text!r}") from None
    if parts.scheme != "http" or not parts.hostname:
        raise argparse.ArgumentTypeError(f"not an http URL: {text!r}")
    return text


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nanoclaw_broker",
        description="Serve a fixed set of NanoClaw verbs to the console: reads and four writes.",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        default=Path(DEFAULT_SOCKET),
        help="the Unix socket this broker serves the console on",
    )
    parser.add_argument(
        "--ncl-socket",
        type=Path,
        default=Path(DEFAULT_NCL_SOCKET),
        help="NanoClaw's control socket (data/ncl.sock)",
    )
    parser.add_argument(
        "--socket-mode",
        type=_mode,
        default=0o660,
        help="octal mode for the broker's socket (default 0660)",
    )
    parser.add_argument(
        "--socket-group",
        type=_gid,
        default=None,
        help="numeric gid to give the broker's socket (the console's group)",
    )
    parser.add_argument(
        "--groups-dir",
        type=Path,
        default=Path(DEFAULT_GROUPS_DIR),
        help="NanoClaw's groups/ directory, mounted read-only (for task-file)",
    )
    parser.add_argument(
        "--mount-allowlist",
        type=Path,
        default=Path(DEFAULT_MOUNT_ALLOWLIST),
        help="NanoClaw's mount-allowlist.json, mounted read-only",
    )
    parser.add_argument(
        "--health-port",
        type=_port,
        default=DEFAULT_HEALTH_PORT,
        help="NanoClaw's loopback /health port (default 3002)",
    )
    parser.add_argument(
        "--onecli-url",
        type=_http_url,
        default=DEFAULT_ONECLI_URL,
        help="OneCLI's API, asked for an agent's proxy credentials (claude-probe)",
    )
    parser.add_argument(
        "--probe-agent-group",
        type=_agent_group,
        default=DEFAULT_PROBE_AGENT_GROUP,
        help="the agent group whose OneCLI credentials claude-probe uses",
    )
    return parser.parse_args(list(argv))


def config_from_args(args: argparse.Namespace) -> BrokerConfig:
    return BrokerConfig(
        socket_path=args.socket,
        ncl_socket=args.ncl_socket,
        socket_mode=args.socket_mode,
        socket_group=args.socket_group,
        groups_dir=args.groups_dir,
        mount_allowlist=args.mount_allowlist,
        health_port=args.health_port,
        onecli_url=args.onecli_url,
        probe_agent_group=args.probe_agent_group,
    )


async def _run(config: BrokerConfig) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await serve(config, stop)
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main(argv: Sequence[str] | None = None) -> int:
    config = config_from_args(parse_args(sys.argv[1:] if argv is None else argv))
    try:
        asyncio.run(_run(config))
    except OSError as exc:
        print(f"nanoclaw_broker: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
