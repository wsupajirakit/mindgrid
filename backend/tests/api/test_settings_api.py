"""Settings and secrets over HTTP: declared keys only, scope rights, values never returned."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.api.deps import CSRF_COOKIE
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import SystemRole

pytestmark = pytest.mark.db
PASSWORD = "Correct horse battery 9"


def _seed() -> None:
    async def run() -> None:
        async with transaction(Actor(None, superadmin=True)) as tx:
            for name, role in (
                ("root", SystemRole.SUPERADMIN),
                ("alice", SystemRole.USER),
                ("bob", SystemRole.USER),
            ):
                await users.create_user(
                    tx,
                    email=f"{name}@example.com",
                    display_name=name,
                    password=PASSWORD,
                    system_role=role,
                )
        await db_engine.dispose()

    asyncio.run(run())


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    _seed()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def _as(client: TestClient, name: str) -> dict[str, str]:
    client.cookies.clear()
    r = client.post("/v1/auth/sign-in", json={"email": f"{name}@example.com", "password": PASSWORD})
    assert r.status_code == 200
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}


def _value(rows: list[dict[str, object]], key: str) -> tuple[object, object]:
    row = next(r for r in rows if r["key"] == key)
    return row["value"], row["source"]


def test_user_setting_overrides_system_default(client: TestClient) -> None:
    root = _as(client, "root")
    assert (
        client.put("/v1/admin/settings/ui.locale", json={"value": "th"}, headers=root).status_code
        == 204
    )
    alice = _as(client, "alice")
    assert _value(client.get("/v1/me/settings").json(), "ui.locale") == ("th", "system")
    assert (
        client.put("/v1/me/settings/ui.locale", json={"value": "it"}, headers=alice).status_code
        == 204
    )
    assert _value(client.get("/v1/me/settings").json(), "ui.locale") == ("it", "user")
    bad = client.put("/v1/me/settings/ui.locale", json={"value": "xx"}, headers=alice)
    assert bad.json()["error"]["code"] == "setting.invalid"
    unknown = client.put("/v1/me/settings/no.such", json={"value": 1}, headers=alice)
    assert unknown.status_code == 404
    assert (
        client.put("/v1/admin/settings/ui.locale", json={"value": "en"}, headers=alice).status_code
        == 403
    )


def test_secrets_are_write_only_and_scoped(client: TestClient) -> None:
    alice = _as(client, "alice")
    pid = client.post(
        "/v1/projects", json={"slug": "alpha", "name": "Alpha"}, headers=alice
    ).json()["id"]
    put = client.put(
        f"/v1/projects/{pid}/secrets/gemini.api_key",
        json={"value": "AIza-very-secret-value-1234"},
        headers=alice,
    )
    assert put.status_code == 200
    assert put.json()["hint"] == "…1234"
    again = client.put(  # replacing a stored secret (rotation)
        f"/v1/projects/{pid}/secrets/gemini.api_key",
        json={"value": "AIza-very-secret-value-5678"},
        headers=alice,
    )
    assert again.status_code == 200, again.text
    assert again.json()["hint"] == "…5678"
    listed = client.get(f"/v1/projects/{pid}/secrets").json()
    assert [s["name"] for s in listed] == ["gemini.api_key"]
    assert "very-secret" not in str(listed)
    _as(client, "bob")
    assert client.get(f"/v1/projects/{pid}/secrets").status_code == 404
    _as(client, "root")
    events = client.get("/v1/audit").json()
    assert any(e["action"] == "secret.put" for e in events)
    assert "very-secret" not in str(events)
