"""Playbooks over HTTP: which projects may run one (superadmin sets the switch and any
project, a project manager only their own projects) and translated titles and summaries."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app

from .people import seed_people, sign_in

pytestmark = pytest.mark.db
PLAYBOOK = "core.table-screen"


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    seed_people()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def _project(client: TestClient, who: str, slug: str) -> str:
    headers = sign_in(client, who)
    return str(
        client.post("/v1/projects", json={"slug": slug, "name": slug}, headers=headers).json()["id"]
    )


def _enabled(client: TestClient, project_id: str) -> bool:
    rows = client.get("/v1/playbooks", params={"project_id": project_id}).json()
    return next(r["enabled"] for r in rows if r["id"] == PLAYBOOK)


def test_superadmin_limits_a_playbook_to_selected_projects(client: TestClient) -> None:
    alpha, beta = _project(client, "alice", "alpha"), _project(client, "bob", "beta")
    root = sign_in(client, "root")
    url = f"/v1/playbooks/{PLAYBOOK}/assignments"
    before = client.get(url).json()
    assert before["all_projects"] is False  # a new project has no playbook until added
    assert {p["name"]: p["enabled"] for p in before["projects"]} == {"alpha": False, "beta": False}
    body = {"all_projects": False, "projects": {alpha: True}}
    after = client.put(url, json=body, headers=root).json()
    assert {p["name"]: (p["enabled"], p["own_choice"]) for p in after["projects"]} == {
        "alpha": (True, True),
        "beta": (False, False),
    }
    sign_in(client, "alice")
    assert _enabled(client, alpha) is True
    sign_in(client, "bob")
    assert _enabled(client, beta) is False
    root = sign_in(client, "root")
    client.put(url, json={"all_projects": True}, headers=root)
    sign_in(client, "bob")
    assert _enabled(client, beta) is True  # switched on for every project


def test_a_manager_assigns_only_their_own_projects(client: TestClient) -> None:
    alpha, beta = _project(client, "alice", "alpha"), _project(client, "bob", "beta")
    url = f"/v1/playbooks/{PLAYBOOK}/assignments"
    alice = sign_in(client, "alice")
    seen = client.get(url).json()["projects"]
    assert [(p["name"], p["can_manage"]) for p in seen] == [("alpha", True)]
    assert _enabled(client, alpha) is False
    assert client.put(url, json={"projects": {alpha: True}}, headers=alice).status_code == 200
    assert _enabled(client, alpha) is True
    assert client.put(url, json={"projects": {beta: False}}, headers=alice).status_code == 404
    denied = client.put(url, json={"all_projects": False}, headers=alice)
    assert denied.json()["error"]["code"] == "auth.superadmin_only"
    missing = client.get("/v1/playbooks/core.nothing/assignments")
    assert missing.json()["error"]["code"] == "playbook.not_found"


def test_translations_ship_with_the_spec_and_a_saved_one_wins(client: TestClient) -> None:
    root = sign_in(client, "root")
    shipped = next(r for r in client.get("/v1/playbooks").json() if r["id"] == PLAYBOOK)
    assert shipped["translations"]["th"]["title"]  # Thai ships with the spec
    url = f"/v1/admin/playbooks/{PLAYBOOK}/translations/th"
    body = {"title": "ตารางคัดกรอง", "summary": "สรุปใหม่"}
    assert client.put(url, json=body, headers=root).status_code == 204
    saved = next(r for r in client.get("/v1/playbooks").json() if r["id"] == PLAYBOOK)
    assert saved["translations"]["th"] == body
    assert saved["title"] == shipped["title"]  # English stays the base text
    bad = client.put(f"/v1/admin/playbooks/{PLAYBOOK}/translations/en", json=body, headers=root)
    assert bad.json()["error"]["code"] == "playbook.bad_locale"
    assert client.delete(url, headers=root).status_code == 204
    again = next(r for r in client.get("/v1/playbooks").json() if r["id"] == PLAYBOOK)
    assert again["translations"]["th"] == shipped["translations"]["th"]
    alice = sign_in(client, "alice")
    assert client.put(url, json=body, headers=alice).status_code == 403
