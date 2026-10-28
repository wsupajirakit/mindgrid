"""Sign-in over HTTP: hardened cookies, CSRF on writes, server-side sign-out, rate limit."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mindgrid.app import create_app
from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.api.deps import CSRF_COOKIE, SESSION_COOKIE
from mindgrid.platform.identity import users

pytestmark = pytest.mark.db
EMAIL, PASSWORD = "alice@example.com", "Correct horse battery 9"


def _seed_user() -> None:
    async def run() -> None:
        async with transaction(Actor(None, superadmin=True)) as tx:
            await users.create_user(tx, email=EMAIL, display_name="Alice", password=PASSWORD)
        await db_engine.dispose()

    asyncio.run(run())


@pytest.fixture
def client(api_db: None) -> Iterator[TestClient]:
    _seed_user()
    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def _sign_in(client: TestClient, password: str = PASSWORD) -> int:
    return client.post("/v1/auth/sign-in", json={"email": EMAIL, "password": password}).status_code


def test_sign_in_sets_hardened_cookies_and_me_works(client: TestClient) -> None:
    r = client.post("/v1/auth/sign-in", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith(SESSION_COOKIE)).lower()
    csrf = next(c for c in cookies if c.startswith(CSRF_COOKIE)).lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/"):
        assert flag in session
    assert "httponly" not in csrf
    assert client.get("/v1/auth/me").json()["display_name"] == "Alice"


def test_writes_need_the_csrf_token_and_sign_out_ends_the_session(client: TestClient) -> None:
    assert _sign_in(client) == 200
    assert client.post("/v1/auth/sign-out").status_code == 403
    token = client.cookies.get(CSRF_COOKIE) or ""
    cross = client.post(
        "/v1/auth/sign-out", headers={"X-CSRF-Token": token, "Sec-Fetch-Site": "cross-site"}
    )
    assert cross.status_code == 403
    assert client.post("/v1/auth/sign-out", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/v1/auth/me").status_code == 401


def test_wrong_password_then_rate_limit(client: TestClient) -> None:
    codes = [_sign_in(client, "wrong password!!") for _ in range(6)]
    assert codes == [401, 401, 401, 401, 401, 429]
    assert _sign_in(client) == 429  # the window still holds


def test_forged_forwarded_for_does_not_reset_the_limit(client: TestClient) -> None:
    def attempt(i: int) -> int:
        forged = {"X-Forwarded-For": f"10.9.{i}.1, 203.0.113.7"}
        body = {"email": EMAIL, "password": "wrong password!!"}
        return client.post("/v1/auth/sign-in", json=body, headers=forged).status_code

    assert [attempt(i) for i in range(6)] == [401, 401, 401, 401, 401, 429]


def test_signed_out_and_forged_cookies_are_refused(client: TestClient) -> None:
    assert client.get("/v1/auth/me").status_code == 401
    client.cookies.set(SESSION_COOKIE, "forged-token")
    r = client.get("/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.required"


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}


def test_profile_name_and_picture(client: TestClient) -> None:
    assert _sign_in(client) == 200
    r = client.patch(
        "/v1/auth/me", json={"display_name": " Alice B ", "avatar": "aurora"}, headers=_csrf(client)
    )
    assert r.status_code == 200
    assert (r.json()["display_name"], r.json()["avatar"]) == ("Alice B", "aurora")
    assert client.get("/v1/auth/me").json()["avatar"] == "aurora"
    bad = client.patch("/v1/auth/me", json={"avatar": "../x"}, headers=_csrf(client))
    assert bad.json()["error"]["code"] == "user.bad_avatar"


def test_own_password_change_needs_the_current_one(client: TestClient) -> None:
    assert _sign_in(client) == 200
    new = "Brand new pass 42"
    wrong = client.post(
        "/v1/auth/password",
        json={"current_password": "nope", "new_password": new},
        headers=_csrf(client),
    )
    assert wrong.json()["error"]["code"] == "auth.bad_password"
    ok = client.post(
        "/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": new},
        headers=_csrf(client),
    )
    assert ok.status_code == 204
    assert client.get("/v1/auth/me").status_code == 200  # this sign-in stays
    client.cookies.clear()
    assert _sign_in(client) == 401
    assert _sign_in(client, new) == 200


def test_a_new_password_must_meet_the_rules(client: TestClient) -> None:
    assert _sign_in(client) == 200

    def change(new: str) -> dict[str, object]:
        r = client.post(
            "/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": new},
            headers=_csrf(client),
        )
        return {"status": r.status_code, **(r.json()["error"] if r.content else {})}

    assert change("Abcdef1")["code"] == "auth.password_short"
    weak = change("abcdefgh1")
    assert weak["code"] == "auth.password_weak"
    assert weak["params"] == {"missing": "upper"}
    assert change("ABCDEFGHI")["params"] == {"missing": "lower,digit"}
    assert change("Abcdefgh1")["status"] == 204  # nine characters, no symbol needed
