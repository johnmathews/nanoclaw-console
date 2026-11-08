"""The broker's command line: socket paths, mode and group, and a clean SIGTERM shutdown."""

import asyncio
import json
import os
import signal
import threading
import time
from pathlib import Path

import pytest

from nanoclaw_broker import __main__ as main_module
from nanoclaw_broker.__main__ import (
    DEFAULT_NCL_SOCKET,
    DEFAULT_SOCKET,
    _run,
    config_from_args,
    main,
    parse_args,
)
from nanoclaw_broker.server import BrokerConfig


def test_defaults() -> None:
    args = parse_args([])
    assert args.socket == Path(DEFAULT_SOCKET) == Path("/run/nanoclaw-console/broker.sock")
    assert args.ncl_socket == Path(DEFAULT_NCL_SOCKET) == Path("/srv/apps/nanoclaw/data/ncl.sock")
    assert args.socket_mode == 0o660
    assert args.socket_group is None


def test_parse_args_reads_every_option() -> None:
    args = parse_args(
        [
            "--socket",
            "/run/nc/broker.sock",
            "--ncl-socket",
            "/srv/data/ncl.sock",
            "--socket-mode",
            "0640",
            "--socket-group",
            "10001",
        ]
    )
    config = config_from_args(args)
    assert config.socket_path == Path("/run/nc/broker.sock")
    assert config.ncl_socket == Path("/srv/data/ncl.sock")
    assert config.socket_mode == 0o640
    assert config.socket_group == 10001


@pytest.mark.parametrize("mode", ["abc", "999", "1777", "-1", "0o660", ""])
def test_bad_socket_modes_are_refused(mode: str) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--socket-mode", mode])
    assert exc.value.code == 2


@pytest.mark.parametrize("group", ["abc", "-1", "1.5", ""])
def test_bad_socket_groups_are_refused(group: str) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--socket-group", group])
    assert exc.value.code == 2


def test_extra_read_defaults() -> None:
    config = config_from_args(parse_args([]))
    assert config.groups_dir == Path("/srv/apps/nanoclaw/groups")
    assert config.mount_allowlist == Path("/etc/nanoclaw/mount-allowlist.json")
    assert config.health_port == 3002
    assert config.onecli_url == "http://127.0.0.1:10254"
    assert config.probe_agent_group == "ag-1779373702795-5wbiev"


def test_extra_read_options() -> None:
    config = config_from_args(
        parse_args(
            [
                "--groups-dir", "/g",
                "--mount-allowlist", "/m/a.json",
                "--health-port", "4000",
                "--onecli-url", "http://127.0.0.1:1234",
                "--probe-agent-group", "ag-1",
            ]
        )
    )  # fmt: skip
    assert config.groups_dir == Path("/g")
    assert config.mount_allowlist == Path("/m/a.json")
    assert config.health_port == 4000
    assert config.onecli_url == "http://127.0.0.1:1234"
    assert config.probe_agent_group == "ag-1"


@pytest.mark.parametrize(
    "argv",
    [
        ["--health-port", "0"],
        ["--health-port", "65536"],
        ["--health-port", "x"],
        ["--probe-agent-group", "../x"],
        ["--probe-agent-group", ""],
        ["--onecli-url", "ftp://127.0.0.1:1"],
        ["--onecli-url", "http://"],
        ["--onecli-url", "http://[::1"],
        ["--onecli-url", "127.0.0.1:10254"],
    ],
)
def test_bad_extra_read_options_are_refused(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def test_parse_args_refuses_unknown_options() -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--verb", "tasks-update"])
    assert exc.value.code == 2


def _kill_when_listening(path: Path) -> threading.Thread:
    def run() -> None:
        for _ in range(500):
            if path.exists():
                break
            time.sleep(0.01)
        os.kill(os.getpid(), signal.SIGTERM)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


async def test_run_serves_until_sigterm(
    short_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sock = short_dir / "broker.sock"
    config = config_from_args(
        parse_args(["--socket", str(sock), "--ncl-socket", str(short_dir / "ncl.sock")])
    )
    thread = _kill_when_listening(sock)
    await asyncio.wait_for(_run(config), 5)
    thread.join(2)
    assert not sock.exists()
    events = [json.loads(line)["event"] for line in capsys.readouterr().out.splitlines()]
    assert events[0] == "listening"
    assert events[-1] == "stopped"
    # The handlers are removed again, so a later SIGTERM is not swallowed by a dead loop.
    assert signal.getsignal(signal.SIGTERM) in (signal.SIG_DFL, signal.default_int_handler)


class FakeRun:
    """Stands in for asyncio.run, with _run stubbed: no second event loop inside pytest."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.configs: list[BrokerConfig] = []

    def __call__(self, stub: tuple[str, BrokerConfig]) -> None:
        self.configs.append(stub[1])
        if self.error is not None:
            raise self.error


def _stub(monkeypatch: pytest.MonkeyPatch, fake: FakeRun) -> None:
    monkeypatch.setattr(main_module, "_run", lambda config: ("run", config))
    monkeypatch.setattr("asyncio.run", fake)


def test_main_runs_the_broker_with_the_parsed_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun()
    _stub(monkeypatch, fake)
    assert main(["--socket", "/run/x/b.sock", "--socket-group", "10001"]) == 0
    assert fake.configs[0].socket_path == Path("/run/x/b.sock")
    assert fake.configs[0].socket_group == 10001


def test_main_reads_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun()
    _stub(monkeypatch, fake)
    monkeypatch.setattr("sys.argv", ["nanoclaw_broker", "--socket", "/run/y.sock"])
    assert main() == 0
    assert fake.configs[0].socket_path == Path("/run/y.sock")


def test_main_fails_cleanly_when_the_socket_path_is_taken(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = FileExistsError("refusing to replace /run/x: it exists and is not a socket")
    _stub(monkeypatch, FakeRun(error))
    assert main([]) == 1
    assert "refusing" in capsys.readouterr().err
