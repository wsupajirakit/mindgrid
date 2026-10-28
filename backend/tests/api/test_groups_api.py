"""User groups over HTTP: a project gives a group a role and every member (also one added
later) gets it; a person's own role wins; category grants work per group too; removing
the group takes its rights away."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app

from .people import seed_people, sign_in

pytestmark = pytest.mark.db


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    seed_people()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def _ids(client: TestClient) -> dict[str, str]:
    return {u["display_name"]: u["id"] for u in client.get("/v1/admin/users").json()}


def test_a_group_role_reaches_every_member_and_an_own_role_wins(client: TestClient) -> None:
    alice = sign_in(client, "alice")
    pid = client.post("/v1/projects", json={"slug": "a", "name": "A"}, headers=alice).json()["id"]
    hr = {"slug": "hr", "name": "HR", "restricted": True}
    cid = client.post(f"/v1/projects/{pid}/categories", json=hr, headers=alice).json()["id"]
    root = sign_in(client, "root")
    ids = _ids(client)
    group = client.post("/v1/admin/groups", json={"name": "Analysts"}, headers=root).json()
    gid = group["id"]
    duplicate = client.post("/v1/admin/groups", json={"name": "analysts"}, headers=root)
    assert duplicate.json()["error"]["code"] == "group.name_taken"
    alice = sign_in(client, "alice")
    assert client.post("/v1/admin/groups", json={"name": "x"}, headers=alice).status_code == 403
    put = client.put(f"/v1/projects/{pid}/groups/{gid}", json={"role": "viewer"}, headers=alice)
    assert put.status_code == 204
    grant = {"level": 1}
    assert (
        client.put(
            f"/v1/categories/{cid}/group-grants/{gid}", json=grant, headers=alice
        ).status_code
        == 204
    )
    sign_in(client, "bob")
    assert client.get(f"/v1/projects/{pid}").status_code == 404  # not in the group yet
    root = sign_in(client, "root")
    added = client.put(f"/v1/admin/groups/{gid}/members/{ids['bob']}", headers=root)
    assert added.status_code == 204
    sign_in(client, "bob")
    assert client.get(f"/v1/projects/{pid}").status_code == 200  # joined later: inherits
    assert [c["slug"] for c in client.get(f"/v1/projects/{pid}/categories").json()] == ["hr"]
    alice = sign_in(client, "alice")
    people = {p["email"]: p for p in client.get(f"/v1/projects/{pid}/people").json()}
    bob = people["bob@example.com"]
    assert (bob["role"], bob["own_role"], [g["name"] for g in bob["via"]]) == (
        "viewer",
        None,
        ["Analysts"],
    )
    own = {"email": "bob@example.com", "role": "editor"}
    client.post(f"/v1/projects/{pid}/members", json=own, headers=alice)
    people = {p["email"]: p for p in client.get(f"/v1/projects/{pid}/people").json()}
    assert people["bob@example.com"]["role"] == "editor"  # his own role wins
    access = client.get(f"/v1/categories/{cid}/access").json()
    assert access["groups"] == [{"group_id": gid, "name": "Analysts", "level": "read"}]
    bob_access = next(p for p in access["people"] if p["email"] == "bob@example.com")
    assert (bob_access["via_groups"], bob_access["level"]) == ("read", "read")
    client.delete(f"/v1/projects/{pid}/members/{ids['bob']}", headers=alice)
    client.delete(f"/v1/projects/{pid}/groups/{gid}", headers=alice)
    sign_in(client, "bob")
    assert client.get(f"/v1/projects/{pid}").status_code == 404  # the group's rights ended


def test_new_users_join_groups_and_the_list_shows_them(client: TestClient) -> None:
    root = sign_in(client, "root")
    gid = client.post("/v1/admin/groups", json={"name": "Ops"}, headers=root).json()["id"]
    body = {
        "email": "c@example.com",
        "display_name": "carol",
        "password": "Correct horse battery 9",
        "group_ids": [gid],
    }
    made = client.post("/v1/admin/users", json=body, headers=root).json()
    assert [g["name"] for g in made["groups"]] == ["Ops"]
    listed = {u["email"]: u for u in client.get("/v1/admin/users").json()}
    assert [g["name"] for g in listed["c@example.com"]["groups"]] == ["Ops"]
    assert client.get("/v1/groups").json()[0]["members"] == 1
    cleared = client.put(
        f"/v1/admin/users/{made['id']}/groups", json={"group_ids": []}, headers=root
    )
    assert cleared.status_code == 204
    assert client.get(f"/v1/admin/groups/{gid}/members").json() == []
    assert client.delete(f"/v1/admin/groups/{gid}", headers=root).status_code == 204
