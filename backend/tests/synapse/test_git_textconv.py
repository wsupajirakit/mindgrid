"""A textconv driver in the repository's own config must never run."""

import subprocess
from pathlib import Path

from mindgrid.synapse import git


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_diff_ignores_textconv(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    marker = tmp_path / "ran"
    repo.mkdir()
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@example.test")
    _run(repo, "config", "user.name", "t")
    _run(repo, "config", "diff.x.textconv", f"touch {marker}; cat")
    (repo / ".gitattributes").write_text("*.txt diff=x\n")
    (repo / "a.txt").write_text("one\n")
    _run(repo, "add", ".")
    _run(repo, "commit", "-q", "-m", "one")
    old = git.head(repo)
    (repo / "a.txt").write_text("two\n")
    _run(repo, "commit", "-q", "-am", "two")
    new = git.head(repo)
    assert [c.path for c in git.changes(repo, old, new)] == ["a.txt"]
    assert "+two" in git.patch(repo, old, new, "a.txt")
    assert not marker.exists()
