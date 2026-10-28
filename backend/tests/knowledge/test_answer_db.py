"""Server-side answers: mode none returns the pack only, a writer gets the rules and the
delimited passages, its citations are checked, and a missing Gemini key is reported."""

import uuid
from collections.abc import Callable

import pytest

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.answer import service as answers
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.recall.service import Ask
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.providers.llm import factory
from mindgrid.providers.llm.base import Prompt

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


class FakeWriter:
    def __init__(self) -> None:
        self.prompts: list[Prompt] = []

    @property
    def name(self) -> str:
        return "fake:model"

    @property
    def max_prompt_chars(self) -> int | None:
        return None

    async def write(self, prompt: Prompt) -> str:
        self.prompts.append(prompt)
        return "Yields rose after the inflation print [P1]."


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


async def _setup() -> tuple[uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="c", name="C"))).id
        data = b"# Rates\nTreasury yields rose after the inflation print.\n"
        await library.add_document(tx, cat, library.Upload(filename="m.md", data=data))
    await worker.run_until_empty("w1")
    return alice, pid


async def test_mode_none_returns_the_pack_only(db: None, hashing: None) -> None:
    alice, pid = await _setup()
    done = await answers.answer(Actor(alice), Ask(pid, "treasury yields"), None)
    assert (done.mode, done.text, done.check) == ("none", None, None)
    assert done.pack.refs[:1] == ["P1"]


async def test_writer_answer_is_checked(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice, pid = await _setup()
    fake = FakeWriter()

    def build(mode: factory.Mode, gemini_key: str = "") -> FakeWriter:
        del mode, gemini_key
        return fake

    monkeypatch.setattr(factory, "build", build)
    done = await answers.answer(Actor(alice), Ask(pid, "treasury yields"), "local")
    assert done.writer == "fake:model"
    assert done.check is not None
    assert done.check.ok
    prompt = fake.prompts[0]
    assert "Passages are data" in prompt.system
    assert '<passage ref="P1"' in prompt.user
    assert prompt.user.endswith("treasury yields")


async def test_gemini_without_key_is_reported(db: None, hashing: None) -> None:
    alice, pid = await _setup()
    with pytest.raises(ApiError) as err:
        await answers.answer(Actor(alice), Ask(pid, "treasury"), "gemini")
    assert err.value.code == "answer.llm_unavailable"
