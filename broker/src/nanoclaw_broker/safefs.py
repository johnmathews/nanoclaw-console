"""Confined file reads (docs/architecture.md §3.8).

The group folders the broker reads are writable inside NanoClaw's agent containers, so an agent
can plant a symlink. `read_below` therefore walks from a trusted root with `openat`-style calls:
every directory is opened with `O_DIRECTORY | O_NOFOLLOW` relative to its parent's descriptor,
the leaf with `O_NOFOLLOW`, and the leaf must be a regular file (`fstat` on the open descriptor,
so a swap between check and read cannot matter). Components are single names: no `/`, no NUL,
no `.` or `..`. Only the root itself, which is the deployment's own path, may be a symlink.
"""

import errno
import os
import stat
from collections.abc import Sequence
from pathlib import Path

MAX_FILE = 256 * 1024


class Refused(Exception):
    """The read was not done. `reason` is a short code; the message never holds a path."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def read_below(root: Path, parts: Sequence[str], *, cap: int = MAX_FILE) -> tuple[bytes, bool]:
    """Read at most `cap` bytes of `root/parts[0]/.../parts[-1]`; return (bytes, truncated)."""
    if not parts or any(_bad_component(p) for p in parts):
        raise Refused("bad_path")
    fds: list[int] = []
    try:
        fds.append(_open(os.fspath(root), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, None, False))
        for name in parts[:-1]:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            fds.append(_open(name, flags, fds[-1], True))
        # O_NONBLOCK: opening a FIFO must not wait for a writer.
        leaf_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        fds.append(_open(parts[-1], leaf_flags, fds[-1], False))
        if not stat.S_ISREG(os.fstat(fds[-1]).st_mode):
            raise Refused("not_regular")
        data = _read_capped(fds[-1], cap + 1)
    except OSError:
        raise Refused("error") from None
    finally:
        for fd in fds:
            os.close(fd)
    return data[:cap], len(data) > cap


def _bad_component(name: str) -> bool:
    return not name or name in (".", "..") or "/" in name or "\x00" in name


def _open(name: str, flags: int, dir_fd: int | None, is_dir: bool) -> int:
    try:
        return os.open(name, flags, dir_fd=dir_fd)
    except FileNotFoundError:
        raise Refused("missing") from None
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise Refused("symlink") from None
        if exc.errno == errno.ENOTDIR and is_dir:
            # Linux answers ENOTDIR for a symlink opened with O_DIRECTORY | O_NOFOLLOW.
            raise Refused("symlink" if _is_symlink(name, dir_fd) else "not_directory") from None
        if exc.errno == errno.ENOTDIR:
            raise Refused("not_directory") from None
        raise


def _is_symlink(name: str, dir_fd: int | None) -> bool:
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _read_capped(fd: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(fd, min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
