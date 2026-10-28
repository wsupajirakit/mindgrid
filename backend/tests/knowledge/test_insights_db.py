"""Answers kept with their questions, and the insights built on them: a client reports its
own answer (checked), nobody attaches one to another person's question, the server keeps
the answers it writes, and the summary and history count what the caller may see."""

import uuid
from collections.abc import Callable

import pytest

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.insights import calls, summary
from mindgrid.knowledge.answer import records
from mindgrid.knowledge.answer import service as answers
from mindgrid.knowledge.library import graph as knowledge_graph
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.recall.service import Ask
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.settings import service as settings_service
from mindgrid.platform.tenancy import categories, members, projects
from mindgrid.platform.tenancy.models import ProjectRole
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.providers.llm import factory as llm_factory
from mindgrid.providers.llm.base import Prompt

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
NOTES = b"# Rates\nTreasury yields rose.\n\n# Credit\nHigh yield spreads widened.\n"


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


class _Writer:
    name = "fake:writer"
    max_prompt_chars = None

    async def write(self, prompt: Prompt) -> str:
        del prompt
        return "Treasury yields rose [P1]."


def _always(writer: object) -> Callable[..., object]:
    def build(*_args: object, **_kwargs: object) -> object:
        return writer

    return build


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice, bob = [
            (
                await users.create_user(
                    tx, email=f"{n}@example.com", display_name=n.title(), password="Test-pass-1"
                )
            ).id
            for n in ("alice", "bob")
        ]
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="Macro"))).id
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="c", name="Notes"))).id
        await members.set_member(tx, pid, bob, ProjectRole.VIEWER)
        await library.add_document(tx, cat, library.Upload(filename="macro.md", data=NOTES))
    await worker.run_until_empty("w1")
    return alice, bob, pid


async def test_reported_answer_is_checked_and_kept_for_its_asker_only(
    db: None, hashing: None
) -> None:
    alice, bob, pid = await _setup()
    async with transaction(Actor(alice)) as tx:
        pack = await answers.context_pack(tx, Ask(pid, "treasury yields"))
    assert pack.recall_id is not None
    written = records.Written("mcp", "mcp:claude-code", "Yields rose [P1].", None)
    async with transaction(Actor(alice)) as tx:
        _, check = await records.report(tx, pack.recall_id, written, pack.refs)
    assert check.ok
    async with transaction(Actor(bob)) as tx:  # a viewer cannot answer someone else's question
        with pytest.raises(ApiError) as err:
            await records.report(tx, pack.recall_id, written, pack.refs)
    assert err.value.code == "answer.question_not_found"
    async with transaction(Actor(alice)) as tx:
        detail = await calls.question(tx, pack.recall_id)
    assert detail["answers"][0]["writer"] == "mcp:claude-code"
    assert detail["answers"][0]["check_ok"] is True
    assert detail["passages"][0]["title"] == "macro.md"
    assert detail["actor"].name == "Alice"


async def test_server_answers_are_kept_and_counted(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm_factory, "build", _always(_Writer()))
    alice, bob, pid = await _setup()
    async with transaction(Actor(alice)) as tx:
        await settings_service.put(tx, Scope.PROJECT, pid, "answer.llm", "local")
    done = await answers.answer(Actor(alice), Ask(pid, "treasury yields"), None, channel="web")
    assert done.text == "Treasury yields rose [P1]."
    async with transaction(Actor(alice)) as tx:
        seen = await summary.summary(tx, 30, None)
        history = await calls.calls(tx, None, None, 50)
    assert seen.totals["questions"] == 1
    assert seen.totals["answers"] == 1
    assert seen.answers_by_channel == [{"channel": "web", "total": 1, "ok": 1}]
    assert seen.hits_by_category[0]["name"] == "Notes"
    assert seen.questions_by_project == [{"project_id": str(pid), "name": "Macro", "total": 1}]
    (question,) = history
    assert (question.kind, question.status, question.channel) == ("question", "answered", "answer")
    assert question.actor is not None
    assert question.actor.name == "Alice"
    async with transaction(Actor(bob)) as tx:  # a viewer sees no one else's questions
        assert await calls.calls(tx, pid, "question", 50) == []
        assert (await summary.summary(tx, 30, pid)).totals["questions"] == 0


async def test_knowledge_graph_links_documents_found_together(db: None, hashing: None) -> None:
    alice, _bob, pid = await _setup()
    async with transaction(Actor(alice)) as tx:
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="d", name="More"))).id
        await library.add_document(
            tx, cat, library.Upload(filename="more.md", data=b"# Rates\nTreasury yields rose.\n")
        )
    await worker.run_until_empty("w1")
    async with transaction(Actor(alice)) as tx:
        await answers.context_pack(tx, Ask(pid, "treasury yields rose"))
        found = await knowledge_graph.build(tx, pid)
    kinds = sorted(n["kind"] for n in found.nodes)
    assert kinds == ["category", "category", "document", "document", "project"]
    together = [e for e in found.edges if e["kind"] == "together"]
    assert len(together) == 1
    assert together[0]["weight"] == 1
