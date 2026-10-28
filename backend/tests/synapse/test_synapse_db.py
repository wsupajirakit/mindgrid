"""Synapse on a throwaway repository: only wanted files are read, personal data is
removed before anything is stored, claims become measurement items, accepted knowledge
becomes document versions, removals remove, code items become a task list."""

import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import select

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.library.models import Document
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import SystemRole
from mindgrid.platform.jobs import worker
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.synapse import sanitize
from mindgrid.synapse import service as synapse
from mindgrid.synapse.understand import Mapping

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.test",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def _write(repo: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


@pytest.fixture
def repo(tmp_path: Path, env: Callable[..., None]) -> Path:
    env(
        MINDGRID_SYNAPSE_ALLOWED_ROOTS=str(tmp_path),
        MINDGRID_ENV="test",
        MINDGRID_EMBEDDING_PROVIDER="hashing",
    )
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(
        repo,
        {
            "skills/a/SKILL.md": (
                "# Rule\nStops sit 1.5 ATR under entry.\nMail me at someone@example.com\n"
                "Key zsk_abcdefgh12345678secret in /home/someone/notes\n"
            ),
            "skills/a/references/evidence.md": (
                "# Evidence\nThe lane won 62% of trades over 10 years.\nHolding: 40 shares of AAA\n"
            ),
            "skills/a/scripts/lib.py": "def stage(x):\n    return x\n",
            "history/run.md": "# private run log\n",
        },
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "one")
    return repo


async def _setup(repo: Path) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        admin = (
            await users.create_user(
                tx,
                email="r@example.com",
                display_name="r",
                password="Test-pass-1",
                system_role=SystemRole.SUPERADMIN,
            )
        ).id
    async with transaction(Actor(admin, superadmin=True)) as tx:
        pid = (await projects.create_project(tx, admin, ProjectInput(slug="m", name="M"))).id
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="k", name="K"))).id
        mapping = Mapping.model_validate(
            {**synapse.templates()[0]["mapping"], "drop_lines": [r"^holding:"]}
        )
        src = await synapse.add_source(
            tx, synapse.NewSource("src", str(repo), mapping, pid, cat), True
        )
    return admin, src.id, cat


async def _check(admin: uuid.UUID, src: uuid.UUID, import_all: bool = False) -> None:
    async with transaction(Actor(admin, superadmin=True)) as tx:
        await synapse.request_check(tx, src, import_all, True)
    await worker.run_until_empty("w1")


async def test_import_sanitises_and_classifies(db: None, repo: Path) -> None:
    admin, src, _ = await _setup(repo)
    await _check(admin, src, import_all=True)
    async with transaction(Actor(admin, superadmin=True)) as tx:
        [proposal] = await synapse.proposals(tx)
    kinds = {(i["kind"], i["path"]) for i in proposal.items}
    assert ("knowledge_update", "skills/a/SKILL.md") in kinds
    assert ("knowledge_update", "skills/a/references/evidence.md") in kinds
    assert ("code_task", "skills/a/scripts/lib.py") in kinds
    assert not any("history/" in p for _, p in kinds)  # excluded, never read
    assert any(i["kind"] == "measure" and "62%" in i["summary"] for i in proposal.items)
    rule = next(
        i for i in proposal.items if i["path"] == "skills/a/SKILL.md" and i["kind"] != "measure"
    )
    text = rule["detail"]["text"]
    assert "someone@example.com" not in text
    assert "zsk_" not in text
    assert "/home/someone" not in text
    evidence = next(
        i for i in proposal.items if i["path"].endswith("evidence.md") and i["kind"] != "measure"
    )
    assert "Holding" not in evidence["detail"]["text"]
    assert proposal.redactions >= 4


async def test_review_applies_knowledge_and_tasks(db: None, repo: Path) -> None:
    admin, src, cat = await _setup(repo)
    await _check(admin, src)  # first check without import: baseline only
    async with transaction(Actor(admin, superadmin=True)) as tx:
        assert await synapse.proposals(tx) == []
    _write(repo, {"skills/a/SKILL.md": "# Rule\nStops sit 2 ATR under entry.\n"})
    (repo / "skills/a/references/evidence.md").unlink()
    _write(repo, {"skills/a/scripts/lib.py": "def stage(x):\n    return x + 1\n"})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "two")
    await _check(admin, src)
    async with transaction(Actor(admin, superadmin=True)) as tx:
        [proposal] = await synapse.proposals(tx)
        by = {(i["kind"], i["path"]): n for n, i in enumerate(proposal.items)}
        await synapse.decide(tx, proposal.id, by[("knowledge_update", "skills/a/SKILL.md")], True)
        await synapse.decide(tx, proposal.id, by[("code_task", "skills/a/scripts/lib.py")], True)
        with pytest.raises(ApiError):
            await synapse.decide(
                tx, proposal.id, by[("code_task", "skills/a/scripts/lib.py")], True
            )
        docs = (await tx.scalars(select(Document).where(Document.category_id == cat))).all()
        md = synapse.tasks_markdown(await synapse.get_proposal(tx, proposal.id))
    assert [(d.title, d.source) for d in docs] == [("skills/a/SKILL.md", "synapse")]
    assert "skills/a/scripts/lib.py" in md
    assert "stage" in md
    assert ("knowledge_remove", "skills/a/references/evidence.md") in by


async def test_sources_must_be_inside_allowed_roots(
    db: None, repo: Path, tmp_path: Path, env: Callable[..., None]
) -> None:
    env(MINDGRID_SYNAPSE_ALLOWED_ROOTS=str(tmp_path / "elsewhere"))
    with pytest.raises(ApiError) as err:
        await _setup(repo)
    assert err.value.code == "synapse.bad_source"


def test_sanitizer_redacts_local_terms_and_tokens() -> None:
    home = str(Path.home())
    out = sanitize.clean(f"see {home}/x and whsec_{'A' * 20} and a@b.test")
    assert home not in out.text
    assert "whsec_" not in out.text
    assert "a@b.test" not in out.text
    assert out.redactions >= 3


def test_patterns_with_inline_flags_and_bad_patterns() -> None:
    out = sanitize.drop_lines("keep\nNAV is 100\nkeep too", [r"(?i)\bnav\b"])
    assert out.text == "keep\nkeep too"
    assert out.redactions == 1
    assert sanitize.clean("Account X", [r"(?i)account"]).text == "[redacted] X"
    with pytest.raises(ValueError, match="does not compile"):
        Mapping.model_validate({"drop_lines": ["("]})
