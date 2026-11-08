"""Confined file reads: every path component is opened without following symlinks."""

import os
import stat
from pathlib import Path

import pytest

from nanoclaw_broker.safefs import MAX_FILE, Refused, read_below

SECRET = "PLANTED-SECRET-outside-file"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "groups" / "g1" / "tasks").mkdir(parents=True)
    (tmp_path / "groups" / "g1" / "tasks" / "a.md").write_text("hello\n")
    return tmp_path / "groups"


def test_reads_a_file_below_the_root(root: Path) -> None:
    assert read_below(root, ("g1", "tasks", "a.md")) == (b"hello\n", False)


def test_a_missing_file_is_missing(root: Path) -> None:
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "nope.md"))
    assert exc.value.reason == "missing"


def test_a_missing_directory_is_missing(root: Path) -> None:
    with pytest.raises(Refused) as exc:
        read_below(root, ("g9", "tasks", "a.md"))
    assert exc.value.reason == "missing"


def test_a_missing_root_is_missing(tmp_path: Path) -> None:
    with pytest.raises(Refused) as exc:
        read_below(tmp_path / "absent", ("g1",))
    assert exc.value.reason == "missing"


@pytest.mark.parametrize(
    "parts",
    [
        ("..", "g1", "tasks", "a.md"),
        ("g1", "..", "g1", "tasks", "a.md"),
        ("g1", "tasks", "..", "tasks", "a.md"),
        ("g1", "tasks", "../a.md"),
        ("g1/tasks", "a.md"),
        ("/etc", "passwd"),
        ("g1", "tasks", "/etc/passwd"),
        (".", "g1", "tasks", "a.md"),
        ("g1", "tasks", ""),
        ("g1", "tasks", "a\x00.md"),
        (),
    ],
)
def test_traversal_and_odd_components_are_refused(root: Path, parts: tuple[str, ...]) -> None:
    (root.parent / "outside.md").write_text(SECRET)
    with pytest.raises(Refused) as exc:
        read_below(root, parts)
    assert exc.value.reason == "bad_path"


def test_a_symlinked_tasks_directory_is_refused(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "a.md").write_text(SECRET)
    (root / "g2").mkdir()
    (root / "g2" / "tasks").symlink_to(outside, target_is_directory=True)
    with pytest.raises(Refused) as exc:
        read_below(root, ("g2", "tasks", "a.md"))
    assert exc.value.reason == "symlink"


def test_a_symlinked_group_directory_is_refused(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    (outside / "tasks").mkdir(parents=True)
    (outside / "tasks" / "a.md").write_text(SECRET)
    (root / "g3").symlink_to(outside, target_is_directory=True)
    with pytest.raises(Refused) as exc:
        read_below(root, ("g3", "tasks", "a.md"))
    assert exc.value.reason == "symlink"


def test_a_symlinked_leaf_is_refused(root: Path, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text(SECRET)
    (root / "g1" / "tasks" / "link.md").symlink_to(tmp_path / "secret.txt")
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "link.md"))
    assert exc.value.reason == "symlink"


def test_a_dangling_symlinked_leaf_is_refused_not_missing(root: Path) -> None:
    (root / "g1" / "tasks" / "dangling.md").symlink_to(root / "nowhere")
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "dangling.md"))
    assert exc.value.reason == "symlink"


def test_a_directory_leaf_is_refused(root: Path) -> None:
    (root / "g1" / "tasks" / "dir.md").mkdir()
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "dir.md"))
    assert exc.value.reason == "not_regular"


def test_a_fifo_leaf_is_refused_without_blocking(root: Path) -> None:
    os.mkfifo(root / "g1" / "tasks" / "pipe.md")
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "pipe.md"))
    assert exc.value.reason == "not_regular"


def test_a_file_where_a_directory_is_expected_is_refused(root: Path) -> None:
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "a.md", "x"))
    assert exc.value.reason == "not_directory"


def test_the_root_may_be_reached_through_a_symlink(root: Path, tmp_path: Path) -> None:
    """Only the configured root is followed (a deployment path); nothing below it is."""
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert read_below(alias, ("g1", "tasks", "a.md"))[0] == b"hello\n"


def test_the_size_cap(root: Path) -> None:
    path = root / "g1" / "tasks" / "big.md"
    path.write_bytes(b"x" * MAX_FILE)
    assert read_below(root, ("g1", "tasks", "big.md")) == (b"x" * MAX_FILE, False)
    path.write_bytes(b"x" * (MAX_FILE + 1))
    data, truncated = read_below(root, ("g1", "tasks", "big.md"))
    assert (len(data), truncated) == (MAX_FILE, True)


def test_an_empty_file(root: Path) -> None:
    (root / "g1" / "tasks" / "empty.md").write_bytes(b"")
    assert read_below(root, ("g1", "tasks", "empty.md")) == (b"", False)


def test_an_unreadable_file_is_refused(root: Path) -> None:
    path = root / "g1" / "tasks" / "locked.md"
    path.write_text("x")
    path.chmod(0)
    try:
        if os.access(path, os.R_OK):  # running as root: permissions do not apply
            pytest.skip("permissions are not enforced for this user")
        with pytest.raises(Refused) as exc:
            read_below(root, ("g1", "tasks", "locked.md"))
        assert exc.value.reason == "error"
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_refused_str_has_no_path(root: Path) -> None:
    with pytest.raises(Refused) as exc:
        read_below(root, ("g1", "tasks", "nope.md"))
    assert str(root) not in str(exc.value)
    assert "nope" not in str(exc.value)
