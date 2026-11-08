"""The broker's command line: two socket paths, and a clear refusal until the server exists."""

from pathlib import Path

import pytest

from nanoclaw_broker.__main__ import NOT_IMPLEMENTED_EXIT, main, parse_args


def test_parse_args_reads_both_sockets() -> None:
    args = parse_args(["--socket", "/run/nc/broker.sock", "--ncl-socket", "/srv/data/ncl.sock"])
    assert args.socket == Path("/run/nc/broker.sock")
    assert args.ncl_socket == Path("/srv/data/ncl.sock")


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--socket", "/run/nc/broker.sock"],
        ["--ncl-socket", "/srv/data/ncl.sock"],
    ],
)
def test_parse_args_requires_both_sockets(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def test_parse_args_refuses_unknown_options() -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--socket", "a", "--ncl-socket", "b", "--verb", "tasks-update"])
    assert exc.value.code == 2


def test_main_says_not_implemented(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--socket", "/run/nc/broker.sock", "--ncl-socket", "/srv/data/ncl.sock"])
    assert code == NOT_IMPLEMENTED_EXIT
    err = capsys.readouterr().err
    assert "not implemented" in err
    assert "/srv/data/ncl.sock" in err


def test_main_reads_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv", ["nanoclaw_broker", "--socket", "/run/a.sock", "--ncl-socket", "/srv/b.sock"]
    )
    assert main() == NOT_IMPLEMENTED_EXIT
