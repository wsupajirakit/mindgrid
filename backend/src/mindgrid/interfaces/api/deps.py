"""Request dependencies: who is calling and a database transaction bound to that principal
for row-level security. Browsers authenticate with the session cookie (+ CSRF); machines
with an API key: a signed request (RFC 9421) carrying an access token. Routes ask for
`Tx`; the transaction commits when the route returns and rolls back when it raises."""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.platform.apikeys import signing
from mindgrid.platform.apikeys import verify as key_verify
from mindgrid.platform.apikeys.models import KeyScope
from mindgrid.platform.identity import sessions
from mindgrid.platform.security import csrf

SESSION_COOKIE = "__Host-mg_session"
CSRF_COOKIE = "__Host-mg_csrf"


READ_METHODS = frozenset({"GET", "HEAD"})
KEY_SCOPE_FIELD = "x-key-scope"


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    superadmin: bool
    session_id: uuid.UUID | None  # None: an API key, not a browser session
    projects: tuple[uuid.UUID, ...] = ()
    api_key_id: uuid.UUID | None = None

    @property
    def actor(self) -> Actor:
        return Actor(user_id=self.user_id, superadmin=self.superadmin, projects=self.projects)


async def request_parts(request: Request) -> signing.RequestParts:
    """What a signature covers, exactly as received (raw path, raw query, body)."""
    return signing.RequestParts(
        method=request.method,
        path=request.scope.get("raw_path", request.url.path.encode()).decode("latin-1"),
        query=request.scope.get("query_string", b"").decode("latin-1"),
        headers={k.lower(): v for k, v in request.headers.items()},
        body=await request.body(),
    )


def key_scope(scope: KeyScope) -> dict[str, Any]:
    """Route option declaring the API-key scope a route needs, when the method alone would
    say otherwise (a read-only search sent as POST): `openapi_extra=key_scope(...)`."""
    return {KEY_SCOPE_FIELD: scope.value}


def needed_scope(request: Request) -> str:
    extra: dict[str, Any] = getattr(request.scope.get("route"), "openapi_extra", None) or {}
    declared: object = extra.get(KEY_SCOPE_FIELD)
    if isinstance(declared, str):
        return declared
    return KeyScope.READ.value if request.method in READ_METHODS else KeyScope.EDIT.value


async def _machine_principal(request: Request) -> Principal:
    caller = await key_verify.verify(await request_parts(request), with_token=True)
    needed = needed_scope(request)
    if needed not in caller.scopes:
        raise ApiError(403, "auth.scope", "the key does not allow this", params={"needed": needed})
    return Principal(
        user_id=caller.owner_user_id,
        superadmin=False,
        session_id=None,
        projects=caller.projects,
        api_key_id=caller.api_key_id,
    )


def _signed_out() -> ApiError:
    return ApiError(401, "auth.required", "sign in first")


async def current_principal(request: Request) -> Principal:
    if "signature-input" in request.headers:
        return await _machine_principal(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise _signed_out()
    async with transaction(SYSTEM) as tx:
        info = await sessions.resolve(tx, token)
    if info is None:
        raise _signed_out()
    async with transaction(Actor(info.user_id, info.superadmin)) as tx:
        if await sessions.is_idle(tx, info.session_id):
            raise _signed_out()
    reason = csrf.failure(request.method, request.headers, token)
    if reason is not None:
        raise ApiError(403, "auth.csrf", reason)
    return Principal(user_id=info.user_id, superadmin=info.superadmin, session_id=info.session_id)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


async def principal_tx(principal: CurrentPrincipal) -> AsyncGenerator[AsyncSession]:
    async with transaction(principal.actor) as tx:
        yield tx


Tx = Annotated[AsyncSession, Depends(principal_tx)]


async def superadmin_principal(principal: CurrentPrincipal) -> Principal:
    if not principal.superadmin:
        raise ApiError(403, "auth.superadmin_only", "superadmin only")
    return principal


SuperadminPrincipal = Annotated[Principal, Depends(superadmin_principal)]
