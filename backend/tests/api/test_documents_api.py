"""Document upload over HTTP: multipart, size cap before parsing, unsupported types."""

import asyncio
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.api.deps import CSRF_COOKIE
from mindgrid.platform.identity import users

pytestmark = pytest.mark.db
PASSWORD = "Correct horse battery 9"


@pytest.fixture
def client(api_db: None, env: Callable[..., None]) -> Iterator[TestClient]:
    env(MINDGRID_MAX_UPLOAD_BYTES="2000")

    async def seed() -> None:
        async with transaction(Actor(None, superadmin=True)) as tx:
            await users.create_user(
                tx, email="alice@example.com", display_name="a", password=PASSWORD
            )
        await db_engine.dispose()

    asyncio.run(seed())
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def test_upload_list_preview_and_limits(client: TestClient) -> None:
    client.post("/v1/auth/sign-in", json={"email": "alice@example.com", "password": PASSWORD})
    headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}
    pid = client.post("/v1/projects", json={"slug": "p", "name": "P"}, headers=headers).json()["id"]
    cid = client.post(
        f"/v1/projects/{pid}/categories", json={"slug": "k", "name": "K"}, headers=headers
    ).json()["id"]
    url = f"/v1/categories/{cid}/documents"
    ok = client.post(
        url,
        files={"file": ("guide.md", b"# Intro\nhello world\n")},
        data={"trust": "verified"},
        headers=headers,
    )
    assert ok.status_code == 201
    doc = ok.json()
    assert (doc["title"], doc["trust"], doc["current_version"]) == ("guide.md", "verified", 1)
    assert [d["id"] for d in client.get(url).json()] == [doc["id"]]
    preview = client.get(f"/v1/documents/{doc['id']}/chunks").json()
    assert preview[0]["heading"] == "Intro"
    big = client.post(url, files={"file": ("big.txt", b"x" * 100_000)}, headers=headers)
    assert big.status_code == 413
    exe = client.post(url, files={"file": ("tool.exe", b"MZ")}, headers=headers)
    assert exe.json()["error"]["code"] == "document.unsupported"


def test_context_pack_answer_and_citation_check(client: TestClient) -> None:
    client.post("/v1/auth/sign-in", json={"email": "alice@example.com", "password": PASSWORD})
    headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}
    pid = client.post("/v1/projects", json={"slug": "p", "name": "P"}, headers=headers).json()["id"]
    cid = client.post(
        f"/v1/projects/{pid}/categories", json={"slug": "k", "name": "K"}, headers=headers
    ).json()["id"]
    data = b"# Rates\nTreasury yields rose after the inflation print.\n"
    client.post(f"/v1/categories/{cid}/documents", files={"file": ("m.md", data)}, headers=headers)
    body = {"query": "treasury yields"}
    pack = client.post(f"/v1/projects/{pid}/context-pack", json=body, headers=headers).json()
    assert pack["version"] == "context-pack/1"
    assert pack["passages"][0]["ref"] == "P1"
    assert "vector" in pack["skipped"]
    assert '<passage ref="P1"' in pack["rendered"]
    done = client.post(f"/v1/projects/{pid}/answer", json=body, headers=headers).json()
    assert (done["mode"], done["answer"]) == ("none", None)
    check = client.post(
        "/v1/citations/verify", json={"answer": "Yes [P2].", "refs": ["P1"]}, headers=headers
    ).json()
    assert (check["ok"], check["unknown"]) == (False, ["P2"])


def test_ready_with_the_database(client: TestClient) -> None:
    assert client.get("/v1/ready").json() == {"status": "ready"}
