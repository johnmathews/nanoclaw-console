"""Typed errors. Each carries the `code` the console sees (docs/architecture.md §3.3)."""

# ncl's own error messages are passed on to the console, cut to this length.
MAX_NCL_MESSAGE = 500


class BrokerError(Exception):
    """An error the broker reports to its client as `{"code", "message"}`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class NclError(BrokerError):
    """ncl answered `ok: false`; `ncl_code` is its own code (`handler-error`, `invalid-args`...)."""

    def __init__(self, ncl_code: str, message: str) -> None:
        super().__init__("ncl_error", f"{ncl_code}: {message[:MAX_NCL_MESSAGE]}")
        self.ncl_code = ncl_code


class NclUnavailable(BrokerError):
    """ncl.sock is missing, refuses connections or cannot be opened: NanoClaw is down."""

    def __init__(self, message: str) -> None:
        super().__init__("unavailable", message)


class NclTimeout(BrokerError):
    """ncl did not answer in time."""

    def __init__(self, message: str) -> None:
        super().__init__("timeout", message)


class NclProtocolError(BrokerError):
    """ncl's reply was not one well-formed frame for our request."""

    def __init__(self, message: str) -> None:
        super().__init__("protocol_error", message)
