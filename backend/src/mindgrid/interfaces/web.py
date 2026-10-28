"""Serve the built web app (web/dist) from the same origin as the API, with security
headers on every response. Unknown non-API paths return index.html (client-side routes)."""

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mindgrid.core import runtime
from mindgrid.core.config import AppSettings, env_field, settings_getter

# script-src 'self' only: the app ships no inline script (theme-init.js is a file).
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ]
)
HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}
HSTS = "max-age=63072000; includeSubDomains"


class WebSettings(AppSettings):
    dist_dir: str = env_field(
        "MINDGRID_WEB_DIST", "", doc="Built web app folder; blank = API only."
    )


get_settings = settings_getter(WebSettings)


class SecurityHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        production = runtime.get_settings().environment == "production"

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers += [(k.encode(), v.encode()) for k, v in HEADERS.items()]
                if production:
                    headers.append((b"strict-transport-security", HSTS.encode()))
            await send(message)

        await self.app(scope, receive, with_headers)


def mount(app: FastAPI, api_prefix: str) -> None:
    dist = get_settings().dist_dir
    if not dist or not (Path(dist) / "index.html").is_file():
        return
    root = Path(dist).resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request) -> Response:
        if path.startswith(api_prefix.strip("/") + "/") or path == api_prefix.strip("/"):
            return Response(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        page = FileResponse(root / "index.html")
        page.headers["cache-control"] = "no-cache"
        return page
