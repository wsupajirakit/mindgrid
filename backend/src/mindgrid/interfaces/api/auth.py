"""/v1/auth: sign in (sets the HttpOnly session cookie + the CSRF cookie), sign out (ends
the session on the server), me (read, change name and picture), own password."""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, transaction
from mindgrid.platform.audit import log as audit
from mindgrid.platform.identity import config as session_config
from mindgrid.platform.identity import passwords, sessions, signin, users
from mindgrid.platform.identity.models import SystemRole, User
from mindgrid.platform.security import config as security_config
from mindgrid.platform.security import csrf, rate_limit

from .deps import CSRF_COOKIE, SESSION_COOKIE, CurrentPrincipal, Principal, Tx

router = APIRouter(prefix="/auth", tags=["auth"])


class SignInBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


class Me(BaseModel):
    id: str
    email: str
    display_name: str
    system_role: SystemRole
    locale: str
    avatar: str = Field("", description="Built-in picture id; empty = initials.")

    @classmethod
    def of(cls, user: User) -> Me:
        return cls(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            system_role=user.system_role,
            locale=user.locale,
            avatar=user.avatar,
        )


class ProfilePatch(BaseModel):
    display_name: str | None = Field(None, max_length=120)
    avatar: str | None = Field(None, max_length=40)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)
    new_password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


def client_ip(request: Request) -> str:
    """The address the nearest proxy saw: the last X-Forwarded-For entry. Earlier entries
    come from the client and can be forged, so they never pick the rate-limit key."""
    forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
    forwarded = [h for h in forwarded if h]
    if forwarded:
        return forwarded[-1][:64]
    return request.client.host if request.client else "unknown"


async def _limit(request: Request, email: str) -> None:
    cfg = security_config.get_settings()
    ip = client_ip(request)
    async with transaction(SYSTEM) as tx:
        wait = await rate_limit.hit(tx, f"signin-ip:{ip}", cfg.signin_ip_limit, cfg.signin_window_s)
        if wait is None:
            key = f"signin:{ip}:{email.strip().lower()}"
            wait = await rate_limit.hit(tx, key, cfg.signin_limit, cfg.signin_window_s)
    if wait is not None:
        raise ApiError(
            429,
            "auth.rate_limited",
            "too many attempts",
            params={"retry_after": wait},
            headers={"Retry-After": str(wait)},
        )


def _cookie(response: Response, name: str, value: str, *, httponly: bool) -> None:
    max_age = session_config.get_settings().ttl_hours * 3600
    response.set_cookie(
        name, value, max_age=max_age, path="/", secure=True, httponly=httponly, samesite="strict"
    )


def _set_cookies(response: Response, token: str) -> None:
    _cookie(response, SESSION_COOKIE, token, httponly=True)  # never readable by scripts
    _cookie(response, CSRF_COOKIE, csrf.token_for(token), httponly=False)  # echoed in a header


@router.post("/sign-in")
async def sign_in(body: SignInBody, request: Request, response: Response) -> Me:
    await _limit(request, body.email)
    agent = request.headers.get("user-agent", "")
    done = await signin.sign_in(body.email, body.password, agent)
    _set_cookies(response, done.token)
    async with transaction(done.actor) as tx:
        user = await users.get_user(tx, done.user_id)
    if user is None:
        raise ApiError(401, "auth.bad_credentials", "email or password is wrong")
    return Me.of(user)


@router.post("/sign-out")
async def sign_out(principal: CurrentPrincipal, tx: Tx, response: Response) -> dict[str, str]:
    if principal.session_id is None:
        raise ApiError(400, "auth.not_a_session", "API keys revoke tokens at /auth/token/revoke")
    await sessions.revoke(tx, principal.session_id)
    await audit.record(tx, "auth.sign_out", target=audit.Target("user", principal.user_id))
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=True, samesite="strict")
    return {"status": "signed_out"}


@router.get("/me")
async def me(principal: CurrentPrincipal, tx: Tx) -> Me:
    user = await users.get_user(tx, principal.user_id)
    if user is None:
        raise ApiError(401, "auth.required", "sign in first")
    return Me.of(user)


async def _own(principal: Principal, tx: AsyncSession) -> User:
    user = await users.get_user(tx, principal.user_id)
    if user is None:
        raise ApiError(401, "auth.required", "sign in first")
    return user


@router.patch("/me")
async def update_me(body: ProfilePatch, principal: CurrentPrincipal, tx: Tx) -> Me:
    """Your own display name and picture."""
    user = await users.update_profile(
        tx, await _own(principal, tx), display_name=body.display_name, avatar=body.avatar
    )
    await audit.record(tx, "user.profile", target=audit.Target("user", user.id))
    return Me.of(user)


@router.post("/password", status_code=204)
async def change_password(body: PasswordChange, principal: CurrentPrincipal, tx: Tx) -> None:
    """Your own password: the current one is required; every other sign-in of yours ends."""
    user = await _own(principal, tx)
    await users.change_password(tx, user, body.current_password, body.new_password)
    await sessions.revoke_all(tx, user.id, keep=principal.session_id)
    await audit.record(tx, "user.password", target=audit.Target("user", user.id))
