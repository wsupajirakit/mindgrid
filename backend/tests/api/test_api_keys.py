"""API keys end to end: issue (superadmin), signed token exchange, signed + token calls,
replay / tampering / window refused, scopes and project limits, refresh rotation with
reuse detection, revocation."""

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.api.deps import CSRF_COOKIE
from mindgrid.platform.apikeys.client import KeyCredentials, Outgoing, signed_headers
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import SystemRole

pytestmark = pytest.mark.db
PASSWORD = "Correct horse battery 9"


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    async def seed() -> None:
        async with transaction(Actor(None, superadmin=True)) as tx:
            for name, role in (("root", SystemRole.SUPERADMIN), ("alice", SystemRole.USER)):
                await users.create_user(
                    tx,
                    email=f"{name}@example.com",
                    display_name=name,
                    password=PASSWORD,
                    system_role=role,
                )
        await db_engine.dispose()

    asyncio.run(seed())
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def _browser(client: TestClient, name: str) -> dict[str, str]:
    client.cookies.clear()
    client.post("/v1/auth/sign-in", json={"email": f"{name}@example.com", "password": PASSWORD})
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}


def _issue_key(client: TestClient, scopes: list[str], projects: list[str]) -> KeyCredentials:
    alice = _browser(client, "alice")
    me = client.get("/v1/auth/me").json()["id"]
    root = _browser(client, "root")
    body = {"owner_user_id": me, "name": "ci", "scopes": scopes, "project_ids": projects}
    issued = client.post("/v1/admin/api-keys", json=body, headers=root).json()
    client.cookies.clear()
    assert alice  # alice's browser session is not used by the key calls
    return KeyCredentials.from_pem(issued["key"]["key_id"], issued["private_key_pem"])


def _call(
    client: TestClient,
    creds: KeyCredentials,
    method: str,
    path: str,
    *,
    body: object = None,
    token: str = "",
) -> tuple[int, Any]:
    raw = json.dumps(body).encode() if body is not None else b""
    headers = signed_headers(creds, Outgoing(method, path, body=raw, token=token))
    if body is not None:
        headers["content-type"] = "application/json"
    r = client.request(method, path, content=raw, headers=headers)
    return r.status_code, r.json() if r.content else {}


def _tokens(client: TestClient, creds: KeyCredentials) -> dict[str, Any]:
    status, out = _call(client, creds, "POST", "/v1/auth/token", body={})
    assert status == 200, out
    return out


def test_signed_calls_scopes_and_replay(client: TestClient) -> None:
    creds = _issue_key(client, ["read"], [])
    access = str(_tokens(client, creds)["access_token"])
    assert _call(client, creds, "GET", "/v1/projects", token=access)[0] == 200
    status, out = _call(
        client, creds, "POST", "/v1/projects", body={"slug": "x", "name": "x"}, token=access
    )
    assert (status, out["error"]["code"]) == (403, "auth.scope")
    headers = signed_headers(creds, Outgoing("GET", "/v1/projects", token=access))
    assert client.get("/v1/projects", headers=headers).status_code == 200
    replay = client.get("/v1/projects", headers=headers)
    assert replay.json()["error"]["code"] == "auth.replay"
    bare = client.get("/v1/projects", headers={"Authorization": f"Signed {access}"})
    assert bare.status_code == 401  # a token alone is useless without the key's signature


def test_tampered_body_and_admin_unreachable(client: TestClient) -> None:
    creds = _issue_key(client, ["read", "edit"], [])
    access = str(_tokens(client, creds)["access_token"])
    headers = signed_headers(
        creds, Outgoing("POST", "/v1/projects", body=b'{"slug":"a","name":"a"}', token=access)
    )
    headers["content-type"] = "application/json"
    tampered = client.post("/v1/projects", content=b'{"slug":"b","name":"b"}', headers=headers)
    assert tampered.json()["error"]["code"] == "auth.signature_invalid"
    assert _call(client, creds, "GET", "/v1/admin/users", token=access)[0] == 403


def test_refresh_rotation_reuse_and_revocation(client: TestClient) -> None:
    creds = _issue_key(client, ["read"], [])
    first = _tokens(client, creds)
    status, second = _call(
        client,
        creds,
        "POST",
        "/v1/auth/token/refresh",
        body={"refresh_token": first["refresh_token"]},
    )
    assert status == 200
    reuse = _call(
        client,
        creds,
        "POST",
        "/v1/auth/token/refresh",
        body={"refresh_token": first["refresh_token"]},
    )
    assert reuse[1]["error"]["code"] == "auth.refresh_reused"
    assert _call(client, creds, "GET", "/v1/projects", token=str(second["access_token"]))[0] == 401
    fresh = _tokens(client, creds)
    _call(client, creds, "POST", "/v1/auth/token/revoke", body={"token": fresh["access_token"]})
    assert _call(client, creds, "GET", "/v1/projects", token=str(fresh["access_token"]))[0] == 401


def test_project_limited_key_sees_only_its_projects(client: TestClient) -> None:
    alice = _browser(client, "alice")
    keep = client.post("/v1/projects", json={"slug": "keep", "name": "K"}, headers=alice).json()
    client.post("/v1/projects", json={"slug": "other", "name": "O"}, headers=alice)
    creds = _issue_key(client, ["read"], [keep["id"]])
    access = str(_tokens(client, creds)["access_token"])
    status, listed = _call(client, creds, "GET", "/v1/projects", token=access)
    assert status == 200
    assert [p["slug"] for p in listed] == ["keep"]


def test_read_key_may_post_a_search(client: TestClient) -> None:
    """Recall is a POST that only reads: the `read` scope is enough (declared on the route)."""
    headers = _browser(client, "alice")
    project = client.post("/v1/projects", json={"slug": "k", "name": "K"}, headers=headers).json()
    creds = _issue_key(client, ["read"], [])
    access = str(_tokens(client, creds)["access_token"])
    path = f"/v1/projects/{project['id']}/recall"
    status, out = _call(client, creds, "POST", path, body={"query": "yields"}, token=access)
    assert status == 200, out
    assert out["hits"] == []


def test_rotate_gives_a_new_pair_and_ends_the_old_key(client: TestClient) -> None:
    old = _issue_key(client, ["read"], [])
    assert _tokens(client, old)["access_token"]
    root = _browser(client, "root")
    listed = {k["key_id"]: k for k in client.get("/v1/admin/api-keys", headers=root).json()}
    rotated = client.post(f"/v1/admin/api-keys/{listed[old.key_id]['id']}/rotate", headers=root)
    assert rotated.status_code == 201, rotated.text
    out = rotated.json()
    assert out["key"]["key_id"] != old.key_id
    assert (out["key"]["name"], out["key"]["scopes"]) == ("ci", ["read"])
    assert "PRIVATE KEY" in out["private_key_pem"]
    again = client.post(f"/v1/admin/api-keys/{listed[old.key_id]['id']}/rotate", headers=root)
    assert again.json()["error"]["code"] == "apikey.revoked"
    client.cookies.clear()
    new = KeyCredentials.from_pem(out["key"]["key_id"], out["private_key_pem"])
    assert _tokens(client, new)["access_token"]
    status, _ = _call(client, old, "POST", "/v1/auth/token", body={})
    assert status == 401
