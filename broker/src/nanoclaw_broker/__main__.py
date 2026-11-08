"""Entry point: `python -m nanoclaw_broker --socket <path> --ncl-socket <path>`.

The scaffold parses its arguments and stops. The server (the verb list, redaction and the cache)
comes in a later unit; until then the broker refuses to start rather than pretend to serve.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

# EX_UNAVAILABLE from sysexits.h: the service is not available yet.
NOT_IMPLEMENTED_EXIT = 69


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Both socket paths are required; anything else is refused (exit 2)."""
    parser = argparse.ArgumentParser(
        prog="nanoclaw_broker",
        description="Serve a fixed, read-mostly set of NanoClaw verbs to the console.",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        required=True,
        help="the Unix socket this broker serves the console on",
    )
    parser.add_argument(
        "--ncl-socket",
        type=Path,
        required=True,
        help="NanoClaw's control socket (data/ncl.sock)",
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    print(
        f"nanoclaw_broker: not implemented yet; would serve {args.socket} "
        f"for NanoClaw at {args.ncl_socket}",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED_EXIT


if __name__ == "__main__":
    sys.exit(main())
