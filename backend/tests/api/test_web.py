"""The built web app is served from the API origin, with security headers everywhere."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from mindgrid.app import create_app


def _dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title></title>app", encoding="utf-8")
    (tmp_path / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "theme-init.js").write_text("void 0", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("outside", encoding="utf-8")
    return tmp_path


def test_spa_fallback_assets_and_api_boundary(tmp_path: Path, env: Callable[..., None]) -> None:
    env(MINDGRID_WEB_DIST=str(_dist(tmp_path)))
    client = TestClient(create_app())
    page = client.get("/projects/123")
    assert page.status_code == 200
    assert "app" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert client.get("/assets/main.js").text == "console.log(1)"
    assert client.get("/theme-init.js").text == "void 0"
    assert client.get("/v1/nope").status_code == 404
    assert "outside" not in client.get("/../secret.txt").text


def test_security_headers_on_api_and_pages(tmp_path: Path, env: Callable[..., None]) -> None:
    env(MINDGRID_WEB_DIST=str(_dist(tmp_path)), MINDGRID_ENV="production")
    client = TestClient(create_app())
    for path in ("/v1/health", "/"):
        headers = client.get(path).headers
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert "max-age=" in headers["strict-transport-security"]
