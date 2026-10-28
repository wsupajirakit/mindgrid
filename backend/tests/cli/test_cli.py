"""`mindgrid admin create-superadmin`: the password is prompted twice, never an argument."""

import asyncio

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.cli import main as cli
from mindgrid.platform.identity.models import SystemRole, User

pytestmark = pytest.mark.db


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    given: list[str] = []
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": given.pop(0))
    return given


def _roles() -> dict[str, SystemRole]:
    async def run() -> dict[str, SystemRole]:
        async with transaction(Actor(None, superadmin=True)) as tx:
            found = {u.email: u.system_role for u in await tx.scalars(select(User))}
        await db_engine.dispose()
        return found

    return asyncio.run(run())


@pytest.mark.usefixtures("api_db")
def test_create_superadmin_prompts_twice(answers: list[str]) -> None:
    runner = CliRunner()
    answers.extend(["Correct horse battery 9"] * 2)
    ok = runner.invoke(cli.app, ["admin", "create-superadmin", "--email", "root@example.com"])
    assert ok.exit_code == 0, ok.output
    assert _roles() == {"root@example.com": SystemRole.SUPERADMIN}
    answers.extend(["Correct horse battery 9", "something else entirely"])
    differ = runner.invoke(cli.app, ["admin", "create-superadmin", "--email", "x@example.com"])
    assert differ.exit_code != 0
    answers.extend(["short"] * 2)
    weak = runner.invoke(cli.app, ["admin", "create-superadmin", "--email", "y@example.com"])
    assert weak.exit_code == 1
    assert "auth.password_short" in weak.output
    answers.extend(["no capitals or digits"] * 2)
    plain = runner.invoke(cli.app, ["admin", "create-superadmin", "--email", "z@example.com"])
    assert plain.exit_code == 1
    assert "auth.password_weak" in plain.output


@pytest.mark.usefixtures("api_db")
def test_create_superadmin_reads_the_password_from_stdin() -> None:
    runner = CliRunner()
    args = ["admin", "create-superadmin", "--email", "ops@example.com", "--password-stdin"]
    ok = runner.invoke(cli.app, args, input="Correct horse battery 9\n")
    assert ok.exit_code == 0, ok.output
    assert _roles() == {"ops@example.com": SystemRole.SUPERADMIN}
