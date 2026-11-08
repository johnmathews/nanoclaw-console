"""Entry point: `python -m nanoclaw_broker`.

Options: `--socket`, `--ncl-socket`, `--socket-mode`, `--socket-group`. Serves the console until
SIGTERM or SIGINT, then removes its socket and exits 0 (docs/architecture.md §3.7).
"""

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from .server import BrokerConfig, serve

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


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nanoclaw_broker",
        description="Serve a fixed, read-only set of NanoClaw verbs to the console.",
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
    return parser.parse_args(list(argv))


def config_from_args(args: argparse.Namespace) -> BrokerConfig:
    return BrokerConfig(
        socket_path=args.socket,
        ncl_socket=args.ncl_socket,
        socket_mode=args.socket_mode,
        socket_group=args.socket_group,
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
