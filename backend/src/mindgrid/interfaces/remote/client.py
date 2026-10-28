"""Signed API calls with automatic tokens: the access token is cached (owner-only file;
useless without the private key) and refreshed before it expires; a rejected token is
replaced once, then the error is raised."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from mindgrid.platform.apikeys.client import KeyCredentials, Outgoing, signed_headers

from . import config as remote_config
from .profiles import Profile, write_private

TOKEN_MARGIN_SECONDS = 30
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
TIMEOUT_SECONDS = 180


class RemoteError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code


class _TokenReply(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class _ErrorBody(BaseModel):
    code: str = "http"
    message: str = ""


class _ErrorReply(BaseModel):
    error: _ErrorBody = _ErrorBody()


def _error(response: httpx.Response) -> RemoteError:
    try:
        body = _ErrorReply.model_validate_json(response.content).error
    except ValidationError:
        body = _ErrorBody(message=response.reason_phrase)
    return RemoteError(response.status_code, body.code, body.message or response.reason_phrase)


@dataclass(slots=True)
class _Tokens:
    access: str = ""
    refresh: str = ""
    expires_at: float = 0.0


class RemoteClient:
    def __init__(self, profile: Profile, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._profile = profile
        self._creds: KeyCredentials = profile.credentials()
        base = profile.server.rstrip("/")
        self._prefix = urlsplit(base).path
        self._http = httpx.AsyncClient(base_url=base, timeout=TIMEOUT_SECONDS, transport=transport)
        self._tokens = self._load_tokens()

    async def __aenter__(self) -> RemoteClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    def _cache(self) -> Path:
        return remote_config.cache_dir() / "tokens" / f"{self._profile.name}.json"

    def _load_tokens(self) -> _Tokens:
        try:
            data = json.loads(self._cache().read_text(encoding="utf-8"))
            if data.get("key_id") == self._profile.key_id:
                return _Tokens(data["access"], data["refresh"], float(data["expires_at"]))
        except OSError, ValueError, KeyError:
            pass
        return _Tokens()

    def _save_tokens(self) -> None:
        t = self._tokens
        body = {
            "key_id": self._profile.key_id,
            "access": t.access,
            "refresh": t.refresh,
            "expires_at": t.expires_at,
        }
        write_private(self._cache(), json.dumps(body))

    async def _send(
        self, method: str, path: str, body: Any, query: dict[str, Any] | None, token: str
    ) -> httpx.Response:
        raw = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
        qs = urlencode({k: v for k, v in (query or {}).items() if v is not None})
        full = f"{self._prefix}{path}"
        headers = signed_headers(self._creds, Outgoing(method, full, qs, raw, token))
        if body is not None:
            headers["content-type"] = "application/json"
        url = f"{path}?{qs}" if qs else path
        return await self._http.request(method, url, content=raw, headers=headers)

    async def _token_call(self, path: str, body: dict[str, str]) -> bool:
        response = await self._send("POST", path, body, None, "")
        if response.status_code != HTTP_OK:
            return False
        data = _TokenReply.model_validate_json(response.content)
        self._tokens = _Tokens(data.access_token, data.refresh_token, time.time() + data.expires_in)
        self._save_tokens()
        return True

    async def _access(self) -> str:
        if self._tokens.access and self._tokens.expires_at - TOKEN_MARGIN_SECONDS > time.time():
            return self._tokens.access
        if self._tokens.refresh and await self._token_call(
            "/v1/auth/token/refresh", {"refresh_token": self._tokens.refresh}
        ):
            return self._tokens.access
        if not await self._token_call("/v1/auth/token", {}):
            raise RemoteError(401, "auth.key", "the API key was refused (expired or revoked?)")
        return self._tokens.access

    async def call(
        self, method: str, path: str, body: Any = None, query: dict[str, Any] | None = None
    ) -> Any:
        response = await self._send(method, path, body, query, await self._access())
        if response.status_code == HTTP_UNAUTHORIZED:
            self._tokens = _Tokens()  # token revoked or expired early: get a new one once
            response = await self._send(method, path, body, query, await self._access())
        if response.is_error:
            raise _error(response)
        return response.json() if response.content else None
