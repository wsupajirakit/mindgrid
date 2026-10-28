"""Projects, members, categories and admin over HTTP, as several users."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app

from .people import PASSWORD, PEOPLE, seed_people, sign_in

pytestmark = pytest.mark.db


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    seed_people()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def test_projects_are_private_until_shared(client: TestClient) -> None:
    alice = sign_in(client, "alice")
    pid = client.post(
        "/v1/projects", json={"slug": "alpha", "name": "Alpha"}, headers=alice
    ).json()["id"]
    client.post(
        f"/v1/projects/{pid}/categories", json={"slug": "markets", "name": "Markets"}, headers=alice
    )
    client.post(
        f"/v1/projects/{pid}/categories",
        json={"slug": "hr", "name": "HR", "restricted": True},
        headers=alice,
    )
    bob = sign_in(client, "bob")
    assert client.get("/v1/projects").json() == []
    assert client.get(f"/v1/projects/{pid}").status_code == 404
    alice = sign_in(client, "alice")
    invite = {"email": "bob@example.com", "role": "viewer"}
    assert client.post(f"/v1/projects/{pid}/members", json=invite, headers=alice).status_code == 201
    bob = sign_in(client, "bob")
    assert [p["slug"] for p in client.get("/v1/projects").json()] == ["alpha"]
    cats = client.get(f"/v1/projects/{pid}/categories").json()
    assert [(c["slug"], c["my_level"]) for c in cats] == [("markets", "read")]
    denied = client.post(
        f"/v1/projects/{pid}/categories", json={"slug": "x", "name": "x"}, headers=bob
    )
    assert denied.status_code == 403
    sign_in(client, "root")
    assert len(client.get("/v1/projects").json()) == 1  # superadmin sees every project


def test_admin_users_is_superadmin_only_and_disabling_ends_sessions(client: TestClient) -> None:
    sign_in(client, "alice")
    assert client.get("/v1/admin/users").status_code == 403
    root = sign_in(client, "root")
    listed = {u["email"]: u["id"] for u in client.get("/v1/admin/users").json()}
    assert set(listed) == {f"{n}@example.com" for n in PEOPLE}
    off = {"status": "disabled"}
    assert (
        client.patch(
            f"/v1/admin/users/{listed['bob@example.com']}", json=off, headers=root
        ).status_code
        == 200
    )
    me = client.patch(f"/v1/admin/users/{listed['root@example.com']}", json=off, headers=root)
    assert me.json()["error"]["code"] == "user.self_change"
    client.cookies.clear()
    r = client.post("/v1/auth/sign-in", json={"email": "bob@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_superadmin_resets_another_password(client: TestClient) -> None:
    root = sign_in(client, "root")
    listed = {u["email"]: u for u in client.get("/v1/admin/users").json()}
    assert listed["bob@example.com"]["avatar"] == ""
    bob = listed["bob@example.com"]["id"]
    new = {"password": "A fresh passphrase 7"}
    assert client.post(f"/v1/admin/users/{bob}/password", json=new, headers=root).status_code == 204
    me = listed["root@example.com"]["id"]
    own = client.post(f"/v1/admin/users/{me}/password", json=new, headers=root)
    assert own.json()["error"]["code"] == "user.self_change"
    client.cookies.clear()
    old = client.post("/v1/auth/sign-in", json={"email": "bob@example.com", "password": PASSWORD})
    assert old.status_code == 401
    fresh = {"email": "bob@example.com", "password": new["password"]}
    assert client.post("/v1/auth/sign-in", json=fresh).status_code == 200
    sign_in(client, "alice")
    assert client.post(f"/v1/admin/users/{bob}/password", json=new).status_code in (403, 401)


def test_audit_names_the_people_it_mentions(client: TestClient) -> None:
    alice = sign_in(client, "alice")
    pid = client.post("/v1/projects", json={"slug": "a", "name": "A"}, headers=alice).json()["id"]
    invite = {"email": "bob@example.com", "role": "viewer"}
    client.post(f"/v1/projects/{pid}/members", json=invite, headers=alice)
    events = client.get("/v1/audit", params={"project_id": pid}).json()
    added = next(e for e in events if e["action"] == "member.set")
    assert (added["actor"]["name"], added["actor"]["email"]) == ("alice", "alice@example.com")
    assert added["people"][added["target_id"]]["email"] == "bob@example.com"


def test_category_access_lists_members_and_grants_open_a_restricted_category(
    client: TestClient,
) -> None:
    alice = sign_in(client, "alice")
    pid = client.post("/v1/projects", json={"slug": "a", "name": "A"}, headers=alice).json()["id"]
    body = {"slug": "hr", "name": "HR", "restricted": True}
    cid = client.post(f"/v1/projects/{pid}/categories", json=body, headers=alice).json()["id"]
    invite = {"email": "bob@example.com", "role": "viewer"}
    client.post(f"/v1/projects/{pid}/members", json=invite, headers=alice)
    rows = {r["email"]: r for r in client.get(f"/v1/categories/{cid}/access").json()["people"]}
    assert (rows["alice@example.com"]["role"], rows["alice@example.com"]["fixed"]) == (
        "owner",
        True,
    )
    assert (rows["bob@example.com"]["level"], rows["bob@example.com"]["granted"]) == (
        "none",
        "none",
    )
    bob_id = rows["bob@example.com"]["user_id"]
    put = client.put(f"/v1/categories/{cid}/grants/{bob_id}", json={"level": 1}, headers=alice)
    assert put.status_code == 204
    rows = {r["email"]: r for r in client.get(f"/v1/categories/{cid}/access").json()["people"]}
    assert rows["bob@example.com"]["level"] == "read"
    sign_in(client, "bob")
    assert [c["slug"] for c in client.get(f"/v1/projects/{pid}/categories").json()] == ["hr"]
    assert client.get(f"/v1/categories/{cid}/access").status_code == 403
