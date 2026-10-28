"""End to end without a network: the remote client signs real requests to the app (ASGI),
gets and caches tokens, and the MCP tools answer through it with the key's rights."""

import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import httpx
import pytest
from mcp import Client
from mcp_types import TextContent

from mindgrid.app import create_app
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.mcp_server import server as mcp_server
from mindgrid.interfaces.remote import knowledge, profiles
from mindgrid.interfaces.remote.client import RemoteClient, RemoteError
from mindgrid.knowledge.library import service as library
from mindgrid.platform.apikeys import keys
from mindgrid.platform.apikeys.models import KeyScope
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.playbooks import overrides

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
NOTES = b"# Rates\nTreasury yields rose after the inflation print.\n"


@pytest.fixture
def client_dirs(tmp_path: Path, env: Callable[..., None]) -> Path:
    env(
        MINDGRID_CONFIG_DIR=str(tmp_path / "cfg"),
        MINDGRID_CLIENT_CACHE_DIR=str(tmp_path / "cache"),
        MINDGRID_ENV="test",
        MINDGRID_EMBEDDING_PROVIDER="hashing",
    )
    return tmp_path


async def _seed(tmp: Path, scopes: tuple[KeyScope, ...]) -> profiles.Profile:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="macro", name="M"))).id
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="c", name="C"))).id
        await library.add_document(tx, cat, library.Upload(filename="notes.md", data=NOTES))
        change = overrides.Change()  # playbooks are off for a project until added
        await overrides.put(tx, (Scope.PROJECT, pid), "core.table-screen", change, False)
    async with transaction(ROOT) as tx:
        issued = await keys.issue(tx, keys.NewKey(alice, "ci", scopes, (), 30))
        key_id = issued.key.key_id
    key_file = tmp / "key.pem"
    key_file.write_text(issued.private_key_pem)
    key_file.chmod(0o600)
    entry = profiles.Profile(
        name="default", server="http://mindgrid.test", key_id=key_id, key_file=str(key_file)
    )
    profiles.save(entry)
    return entry


def _connect(profile: profiles.Profile) -> Callable[[], RemoteClient]:
    transport = httpx.ASGITransport(app=create_app())
    return lambda: RemoteClient(profile, transport=transport)


async def test_client_signs_caches_tokens_and_reads(db: None, client_dirs: Path) -> None:
    profile = await _seed(client_dirs, (KeyScope.READ,))
    connect = _connect(profile)
    async with connect() as client:
        assert [p["slug"] for p in await knowledge.projects(client)] == ["macro"]
        found = await knowledge.pack(client, "macro", "treasury yields")
    assert found["passages"][0]["ref"] == "P1"
    cache = client_dirs / "cache" / "tokens" / "default.json"
    assert json.loads(cache.read_text())["access"]
    assert oct(cache.stat().st_mode)[-3:] == "600"
    async with connect() as client:  # the cached token is reused, then a write is refused
        with pytest.raises(RemoteError) as err:
            await knowledge.answer(client, "macro", "treasury")
    assert err.value.code == "auth.scope"


async def test_key_file_readable_by_others_is_refused(db: None, client_dirs: Path) -> None:
    profile = await _seed(client_dirs, (KeyScope.READ,))
    await anyio.Path(profile.key_file).chmod(0o644)
    with pytest.raises(PermissionError):
        profile.credentials()


async def test_mcp_tools_answer_through_the_key(db: None, client_dirs: Path) -> None:
    profile = await _seed(client_dirs, (KeyScope.READ, KeyScope.RUN))
    connect = _connect(profile)

    @asynccontextmanager
    async def opened() -> AsyncGenerator[RemoteClient]:
        async with connect() as client:
            yield client

    server = mcp_server.build(opened)
    async with Client(server) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        assert {
            "list_projects",
            "recall",
            "answer",
            "verify_citations",
            "list_playbooks",
            "run_playbook",
        } <= names
        result = await mcp.call_tool("recall", {"project": "macro", "question": "treasury"})
        text = "".join(c.text for c in result.content if isinstance(c, TextContent))
        assert '<passage ref="P1"' in text
        assert "Rules:" in text
        check = await mcp.call_tool("verify_citations", {"answer": "Yes [P9].", "refs": ["P1"]})
        assert check.structured_content is not None
        assert check.structured_content["unknown"] == ["P9"]
        recall_id = text.rsplit("recall_id: ", 1)[1].strip()
        kept = await mcp.call_tool(
            "verify_citations",
            {"answer": "Yields rose [P1].", "refs": ["P1"], "recall_id": recall_id},
        )
        assert kept.structured_content is not None
        assert kept.structured_content["kept"] is True
        assert kept.structured_content["cited"] == ["P1"]
        missing = await mcp.call_tool("recall", {"project": "nope", "question": "x"})
        assert missing.is_error


async def test_playbooks_listed_and_run_through_the_key(db: None, client_dirs: Path) -> None:
    profile = await _seed(client_dirs, (KeyScope.READ, KeyScope.RUN))
    connect = _connect(profile)
    rows = [{"name": "a", "score": 3}, {"name": "b", "score": 9}]
    async with connect() as client:
        listed = await knowledge.playbooks(client, "macro")
        assert "core.table-screen" in {p["id"] for p in listed}
        request = {
            "playbook": "core.table-screen",
            "params": {"top_n": 1},
            "inputs": {"rows": rows},
            "wait_seconds": 0,
        }
        started = await knowledge.run_playbook(client, "macro", request)
        assert started["status"] == "queued"
        await worker.run_until_empty("w1")
        done = await client.call("GET", f"/v1/runs/{started['id']}")
    assert done["status"] == "done"
    assert done["outputs"]["rows"] == [rows[1]]
