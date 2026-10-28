"""Hybrid recall over real rows: retrievers agree on the right passage, Thai text is found
by trigram, restricted categories stay hidden, and an unindexed space degrades to keyword."""

import uuid
from collections.abc import Callable

import pytest

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.recall import service as recall
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.settings import service as settings_service
from mindgrid.platform.tenancy import categories, members, projects
from mindgrid.platform.tenancy.models import ProjectRole
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.providers.llm import factory as llm_factory
from mindgrid.providers.llm.base import Prompt, WriterError

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


def _returning(writer: object) -> Callable[..., object]:
    """A stand-in for the writer factory that always builds `writer`."""

    def build(*_args: object, **_kwargs: object) -> object:
        return writer

    return build


MACRO = (
    b"# Rates\nTreasury yields rose after the inflation print.\n"
    b"# Credit\nHigh yield spreads widened.\n"
)
THAI = "# ตลาด\nธนาคารกลางส่งสัญญาณว่าดอกเบี้ยขาขึ้นจะจบในไตรมาสหน้า\n".encode()


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """alice owns a project: `open` holds macro notes and Thai notes, `hr` is restricted;
    bob is a viewer."""
    async with transaction(ROOT) as tx:
        alice, bob = [
            (
                await users.create_user(
                    tx, email=f"{n}@example.com", display_name=n, password="Test-pass-1"
                )
            ).id
            for n in ("alice", "bob")
        ]
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        open_cat = (
            await categories.create_category(tx, pid, CategoryInput(slug="open", name="O"))
        ).id
        hr = (
            await categories.create_category(
                tx, pid, CategoryInput(slug="hr", name="H", restricted=True)
            )
        ).id
        await members.set_member(tx, pid, bob, ProjectRole.VIEWER)
        for name, data, cat in (
            ("macro.md", MACRO, open_cat),
            ("th.md", THAI, open_cat),
            ("pay.md", b"# Pay\nTreasury bonus for staff.\n", hr),
        ):
            await library.add_document(tx, cat, library.Upload(filename=name, data=data))
    return alice, bob, pid, open_cat, hr


async def _ask(actor: Actor, pid: uuid.UUID, query: str, **kw: object) -> recall.Recall:
    async with transaction(actor) as tx:
        return await recall.recall(tx, recall.Ask(pid, query, **kw))  # type: ignore[arg-type]


async def test_hybrid_ranks_the_matching_passage_first(db: None, hashing: None) -> None:
    alice, _bob, pid, _open, _hr = await _setup()
    await worker.run_until_empty("w1")
    out = await _ask(Actor(alice), pid, "treasury yields inflation")
    assert "vector" not in out.skipped  # reranking is off in tests: noted, not an error
    assert out.space == "hashing:bag-of-words@64"
    top = out.hits[0]
    assert top.heading == "Rates"
    assert top.title == "macro.md"
    assert {"vector", "keyword"} <= set(top.ranks)


async def test_thai_text_found_by_trigram(db: None, hashing: None) -> None:
    alice, _bob, pid, _open, _hr = await _setup()
    out = await _ask(Actor(alice), pid, "ดอกเบี้ยขาขึ้น")
    assert out.hits
    assert out.hits[0].title == "th.md"
    assert "trigram" in out.hits[0].ranks


async def test_restricted_category_hidden_from_viewer(db: None, hashing: None) -> None:
    alice, bob, pid, _open, hr = await _setup()
    await worker.run_until_empty("w1")
    owner_titles = {h.title for h in (await _ask(Actor(alice), pid, "treasury")).hits}
    viewer_titles = {h.title for h in (await _ask(Actor(bob), pid, "treasury")).hits}
    assert "pay.md" in owner_titles
    assert "pay.md" not in viewer_titles
    assert "macro.md" in viewer_titles
    with pytest.raises(ApiError) as err:
        await _ask(Actor(bob), pid, "treasury", category_ids=(hr,))
    assert err.value.code == "category.not_found"  # its existence is not revealed


async def test_unindexed_space_falls_back_to_keyword(db: None, hashing: None) -> None:
    alice, _bob, pid, open_cat, _hr = await _setup()
    out = await _ask(Actor(alice), pid, "spreads", category_ids=(open_cat,))
    assert "vector" in out.skipped
    assert out.hits[0].heading == "Credit"


async def test_empty_query_refused(db: None, hashing: None) -> None:
    alice, _bob, pid, _open, _hr = await _setup()
    with pytest.raises(ApiError) as err:
        await _ask(Actor(alice), pid, "   ")
    assert err.value.code == "recall.empty_query"


class _Rewriter:
    name = "fake:rewriter"
    max_prompt_chars = None

    def __init__(self, reply: str = "", fail: bool = False) -> None:
        self.reply, self.fail = reply, fail

    async def write(self, prompt: Prompt) -> str:
        if self.fail:
            raise WriterError("down")
        assert "Question: " in prompt.user
        return self.reply


async def _rewrite_on(alice: uuid.UUID, pid: uuid.UUID) -> None:
    async with transaction(Actor(alice)) as tx:
        await settings_service.put(tx, Scope.PROJECT, pid, "recall.rewrite", "local")


async def test_rewritten_query_adds_candidates(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice, _bob, pid, _open, _hr = await _setup()
    await worker.run_until_empty("w1")
    question = "why did borrowing costs climb"
    before = await _ask(Actor(alice), pid, question)
    await _rewrite_on(alice, pid)
    monkeypatch.setattr(llm_factory, "build", _returning(_Rewriter("Query: treasury yields rose")))
    out = await _ask(Actor(alice), pid, question)
    assert out.rewritten == "treasury yields rose"
    assert "keyword_rewrite" in out.hits[0].ranks
    assert "Treasury yields rose" in out.hits[0].text
    assert len(out.hits) >= len(before.hits)


async def test_failing_rewriter_is_skipped(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice, _bob, pid, _open, _hr = await _setup()
    await worker.run_until_empty("w1")
    await _rewrite_on(alice, pid)
    monkeypatch.setattr(llm_factory, "build", _returning(_Rewriter(fail=True)))
    out = await _ask(Actor(alice), pid, "treasury yields inflation")
    assert out.skipped["rewrite"].startswith("rewriting failed")
    assert out.hits  # the original question still answers
    assert out.rewritten == ""
