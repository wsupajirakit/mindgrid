"""Read-only git access to a source repository: the current commit, the files changed
between two commits, a file's content at a commit and its patch. Fixed argument lists,
no shell, no external diff tools, a path that must sit under an allowed root."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import config as synapse_config

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's well-known empty tree


class GitError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Change:
    status: str  # A added, M modified, D deleted, R renamed (as A + D)
    path: str


def check_path(path: str) -> Path:
    resolved = Path(path).resolve()
    roots = [Path(r).resolve() for r in synapse_config.get_settings().allowed_roots]
    if not any(resolved == r or r in resolved.parents for r in roots):
        raise GitError(
            "the repository is outside the allowed roots (MINDGRID_SYNAPSE_ALLOWED_ROOTS)"
        )
    if not (resolved / ".git").exists():
        raise GitError("not a git repository")
    return resolved


def _git(repo: Path, *args: str) -> str:
    # Fixed program and options; `repo` passed check_path, the rest are revisions/paths.
    # The repository may belong to another account (a mounted volume): trust exactly this
    # one, and never let its config run anything (no hooks, no fsmonitor, no pager).
    safety = [
        "-c",
        f"safe.directory={repo}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.pager=cat",
    ]
    command = ["git", "-C", str(repo), *safety, "-c", "core.quotepath=off", *args]
    timeout = synapse_config.get_settings().git_timeout_seconds
    try:
        done = subprocess.run(command, capture_output=True, check=True, text=True, timeout=timeout)  # noqa: S603
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise GitError(f"git {args[0]} failed") from err
    return done.stdout


def head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").strip()


def changes(repo: Path, old: str | None, new: str) -> list[Change]:
    out = _git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--name-status",
        "--no-renames",
        old or EMPTY_TREE,
        new,
    )
    found: list[Change] = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if path:
            found.append(Change(status[:1], path))
    return found


def content(repo: Path, commit: str, path: str) -> str | None:
    """The file at `commit` (None when deleted, binary or too large)."""
    try:
        size = int(_git(repo, "cat-file", "-s", f"{commit}:{path}").strip())
    except GitError:
        return None
    if size > synapse_config.get_settings().max_file_bytes:
        return None
    text = _git(repo, "show", f"{commit}:{path}")
    return None if "\x00" in text else text


def patch(repo: Path, old: str | None, new: str, path: str) -> str:
    # --no-textconv: a textconv driver in the repository's config would run a command.
    return _git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--unified=2",
        old or EMPTY_TREE,
        new,
        "--",
        path,
    )
