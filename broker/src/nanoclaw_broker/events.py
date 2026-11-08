"""The broker's log: one JSON object per line on stdout. Callers never pass reply data here."""

import json
import sys
from datetime import UTC, datetime
from typing import TextIO


class EventLog:
    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream

    def emit(self, event: str, **fields: object) -> None:
        record: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event": event,
        }
        record.update(fields)
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
