"""Eval runs are stored with their setup; the recall log keeps questions for their asker
and the project's managers only, and the purge removes expired rows."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select

from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.answer import service as answers
from mindgrid.knowledge.evals import judge, runner
from mindgrid.knowledge.evals import log as recall_log
from mindgrid.knowledge.evals.models import RecallEvent
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.recall.service import Ask
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import handlers, worker
from mindgrid.platform.settings import service as settings_service
from mindgrid.platform.tenancy import categories, members, projects
from mindgrid.platform.tenancy.models import ProjectRole
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.providers.llm import factory as llm_factory
from mindgrid.providers.llm.base import Prompt

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


def _returning(writer: object) -> Callable[..., object]:
    """A stand-in for the writer factory that always builds `writer`."""

    def build(*_args: object, **_kwargs: object) -> object:
        return writer

    return build


NOTES = b"# Rates\nTreasury yields rose.\n\n# Credit\nHigh yield spreads widened.\n"


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
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
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="c", name="C"))).id
        await members.set_member(tx, pid, bob, ProjectRole.VIEWER)
        await library.add_document(tx, cat, library.Upload(filename="macro.md", data=NOTES))
    await worker.run_until_empty("w1")
    return alice, bob, pid


async def test_eval_run_scores_and_stores(db: None, hashing: None) -> None:
    alice, _bob, pid = await _setup()
    golden = runner.GoldenSet(
        name="basics",
        k=3,
        cases=[
            runner.Case(query="treasury yields", expect=["macro#rates"]),
            runner.Case(query="spreads widened", expect=["#credit"]),
            runner.Case(query="chocolate cake recipe", expect=[]),
        ],
    )
    async with transaction(Actor(alice)) as tx:
        done = await runner.run(tx, pid, golden)
    assert done.metrics["cases"] == 3
    assert done.metrics["hit_at_k"] == 1.0
    assert done.metrics["abstention"] == 1.0  # off-topic: nothing returned
    assert done.setup["space"] == "hashing:bag-of-words@64"
    async with transaction(ROOT) as tx:  # the operator command (no account) may run too
        await runner.run(tx, pid, golden.model_copy(update={"name": "operator"}))
    async with transaction(Actor(alice)) as tx:
        assert [r.name for r in await runner.list_runs(tx, pid)] == ["operator", "basics"]


async def _count(actor: Actor) -> int:
    async with transaction(actor) as tx:
        return int(await tx.scalar(select(func.count()).select_from(RecallEvent)) or 0)


async def test_recall_log_privacy_and_purge(
    db: None, hashing: None, owner_sql: Callable[[str], Awaitable[None]]
) -> None:
    alice, bob, pid = await _setup()
    async with transaction(Actor(bob)) as tx:
        await answers.context_pack(tx, Ask(pid, "treasury"))
    async with transaction(Actor(alice)) as tx:
        await answers.context_pack(tx, Ask(pid, "spreads"))
    assert await _count(Actor(bob)) == 1  # a viewer sees only their own questions
    assert await _count(Actor(alice)) == 2  # the project owner manages the project
    await owner_sql(
        "update recall_events set created_at = now() - interval '91 days' where query = 'treasury'"
    )
    await worker.run_due({})
    assert await _count(Actor(alice)) == 1
    assert "knowledge.purge_recall_log" in handlers.periodic()
    assert recall_log.purge is not None


class _JudgeAndAnswer:
    """One fake model: answers from the pack, and grades as the judge."""

    name = "fake:llm"
    max_prompt_chars = None

    def __init__(self) -> None:
        self.judged: list[str] = []

    async def write(self, prompt: Prompt) -> str:
        if prompt.system == judge.RULES:
            self.judged.append(prompt.user)
            graded = "yes" if "<answer>" in prompt.user else "partly"
            return f'Sure: {{"context": "{graded}", "faithfulness": 0.75, "reason": "ok"}}'
        return "Treasury yields rose [P1]."


GOLDEN = runner.GoldenSet(
    name="judged",
    k=3,
    cases=[
        runner.Case(query="treasury yields", expect=["macro#rates"]),
        runner.Case(query="chocolate cake recipe", expect=[]),
    ],
)


async def test_judge_grades_context_and_faithfulness(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _JudgeAndAnswer()
    monkeypatch.setattr(llm_factory, "build", _returning(fake))
    alice, bob, pid = await _setup()
    async with transaction(Actor(alice)) as tx:
        await settings_service.put(tx, Scope.PROJECT, pid, "answer.llm", "local")
        run = await runner.run(tx, pid, GOLDEN)
        await judge.enqueue(tx, run, "local")
    assert await worker.run_until_empty("w1") == 1
    assert len(fake.judged) == 1  # the off-topic case is not graded
    assert "<answer>\nTreasury yields rose [P1]." in fake.judged[0]
    async with transaction(Actor(bob)) as tx:  # project viewers read judgements
        (graded,) = (await judge.for_runs(tx, [run.id]))[run.id]
    assert graded.metrics == {
        "judged": 1,
        "failed": 0,
        "judge_context": 1.0,
        "judge_faithfulness": 0.75,
        "answered": 1,
    }
    assert (graded.judge, graded.answerer) == ("fake:llm", "fake:llm")


async def test_judge_without_answers_and_bad_replies(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _JudgeAndAnswer()
    monkeypatch.setattr(llm_factory, "build", _returning(fake))
    alice, _bob, pid = await _setup()
    async with transaction(Actor(alice)) as tx:
        run = await runner.run(tx, pid, GOLDEN)  # answer.llm stays none: nothing to grade
    graded = await judge.judge_run(Actor(alice), run.id, "local")
    assert graded.answerer == ""
    assert graded.metrics["judge_context"] == 0.5
    assert graded.cases[0]["faithfulness"] is None
    assert judge.parse('noise {"context": "no", "faithfulness": null} tail').context == "no"
    with pytest.raises(ValueError, match="no JSON"):
        judge.parse("I cannot grade this")
