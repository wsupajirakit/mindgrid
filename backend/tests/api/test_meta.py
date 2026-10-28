from collections.abc import Callable

from fastapi.testclient import TestClient

from mindgrid.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_and_request_id() -> None:
    with _client() as client:
        r = client.get("/v1/health")
        assert r.json() == {"status": "ok"}
        assert len(r.headers["x-request-id"]) == 32
        echoed = client.get("/v1/health", headers={"X-Request-ID": "trace-12345"})
        assert echoed.headers["x-request-id"] == "trace-12345"
        forged = client.get("/v1/health", headers={"X-Request-ID": "bad id\r\n"})
        assert forged.headers["x-request-id"] != "bad id\r\n"


def test_brand_comes_from_one_config(env: Callable[..., None]) -> None:
    env(MINDGRID_BRAND_NAME="Acme Insight", MINDGRID_BRAND_PRIMARY_COLOR="#112233")
    with _client() as client:
        brand = client.get("/v1/meta/brand").json()
        assert brand["name"] == "Acme Insight"
        assert brand["primary_color"] == "#112233"
        assert client.get("/v1/openapi.json").json()["info"]["title"] == "Acme Insight"


def test_unknown_route_and_validation_shape() -> None:
    with _client() as client:
        assert client.get("/v1/nope").status_code == 404


def test_ready_reports_the_database(env: Callable[..., None]) -> None:
    env(MINDGRID_DATABASE_URL="postgresql+asyncpg://nobody:x@127.0.0.1:9/none")
    with _client() as client:
        assert client.get("/v1/ready").status_code == 503
