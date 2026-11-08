"""The audit log of the four actions (docs/architecture.md §4.9).

One JSON line per attempt that passed the Access check, in `<AUDIT_DIR>/audit.jsonl`, and the same
line on stdout (so `docker logs` and Loki have it too). The file is opened append-only for each
attempt *before* anything is sent to the broker: if it cannot be opened, the action is refused
(fail closed) rather than done unaudited. Nothing here ever rewrites or truncates the file.
"""

import errno
import json
import logging
import os
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

logger = logging.getLogger(__name__)

AUDIT_FILE = "audit.jsonl"
DEFAULT_MAX_READ = 1024 * 1024  # the audit page reads at most the last MiB of the file
DEFAULT_RECENT = 200

_OPEN_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


class AuditUnavailable(Exception):
    """The audit file cannot be opened for appending. The type name is all that is logged."""


@dataclass(frozen=True)
class Recent:
    available: bool
    entries: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False


class AuditWriter:
    """An audit file held open across one action, so a failure to open it is known first."""

    def __init__(self, log: "AuditLog", fd: int) -> None:
        self._log = log
        self._fd = fd

    def write(self, entry: Mapping[str, object]) -> None:
        """Append one line, sync it, then echo it. A failed append is raised after the echo."""
        line = _line(entry)
        try:
            with self._log.lock:
                # A regular file can take less than the whole line (a full disk): finish it, or
                # raise, so a cut line is never reported as written.
                view = memoryview(line)
                while view:
                    written = os.write(self._fd, view)
                    if written <= 0:
                        raise OSError(errno.EIO, "the audit log took no bytes")
                    view = view[written:]
                os.fsync(self._fd)  # a few lines a week: cheap, and the line outlives a crash
        finally:
            self._log.echo(entry)

    def __enter__(self) -> "AuditWriter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        os.close(self._fd)


class AuditLog:
    def __init__(
        self,
        directory: Path,
        *,
        stream: TextIO | None = None,
        max_read: int = DEFAULT_MAX_READ,
    ) -> None:
        self.directory = directory
        self.path = directory / AUDIT_FILE
        self._stream = stream
        self._max_read = max_read
        self.lock = threading.Lock()

    def open(self) -> AuditWriter:
        """The file opened for appending (created 0600), or `AuditUnavailable`.

        `O_NOFOLLOW` refuses a symlink in place of the file, so the log cannot be pointed elsewhere.
        """
        try:
            fd = os.open(self.path, _OPEN_FLAGS, 0o600)
        except OSError:
            raise AuditUnavailable from None
        return AuditWriter(self, fd)

    def writable(self) -> bool:
        try:
            with self.open():
                return True
        except AuditUnavailable:
            return False

    def echo(self, entry: Mapping[str, object]) -> None:
        """The line on stdout. Never raises: the file is the record, stdout a copy."""
        stream = self._stream if self._stream is not None else sys.stdout
        try:
            stream.write(json.dumps({"event": "audit", **entry}, sort_keys=True) + "\n")
            stream.flush()
        except Exception:  # a broken stdout must not stop an audited action
            logger.error("Audit line could not be echoed to stdout")

    def recent(self, limit: int = DEFAULT_RECENT) -> Recent:
        """The last `limit` entries, newest first, from at most the last `max_read` bytes."""
        try:
            fd = os.open(self.path, _READ_FLAGS)
        except FileNotFoundError:
            return Recent(available=self.directory.is_dir())
        except OSError:
            return Recent(available=False)
        try:
            size = os.fstat(fd).st_size
            start = max(0, size - self._max_read)
            os.lseek(fd, start, os.SEEK_SET)
            raw = _read_all(fd, size - start)
        except OSError:
            return Recent(available=False)
        finally:
            os.close(fd)
        lines = raw.split(b"\n")
        cut = start > 0
        if cut:
            lines = lines[1:]  # the first line was cut in the middle
        entries: list[dict[str, Any]] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(value, dict):
                continue
            if len(entries) == limit:
                return Recent(available=True, entries=entries, truncated=True)
            entries.append(value)
        return Recent(available=True, entries=entries, truncated=cut)


def _line(entry: Mapping[str, object]) -> bytes:
    # json.dumps escapes newlines inside strings, so a value can never start a second line.
    return (json.dumps(dict(entry), sort_keys=True) + "\n").encode()


def _read_all(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    while size > 0:
        chunk = os.read(fd, min(size, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)
