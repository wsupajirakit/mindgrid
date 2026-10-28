"""/v1/auth/token*: API keys exchange a signed request for tokens, refresh them (rotating),
and revoke them. Every call here is signed with the key (RFC 9421, ±window, one-time
nonce); no secret ever travels in the request."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mindgrid.db.session import transaction
from mindgrid.platform.apikeys import tokens
from mindgrid.platform.apikeys import verify as key_verify
from mindgrid.platform.audit import log as audit

from .deps import request_parts

router = APIRouter(prefix="/auth/token", tags=["api keys"])


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Signed"  # noqa: S105 — the auth scheme name, not a secret
    expires_in: int


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class RevokeBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def _out(pair: tokens.TokenPair) -> TokenOut:
    return TokenOut(
        access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in
    )


@router.post("")
async def issue(request: Request) -> TokenOut:
    caller = await key_verify.verify(await request_parts(request), with_token=False)
    pair = await tokens.issue_pair(caller.actor, caller.api_key_id)
    async with transaction(caller.actor) as tx:
        await audit.record(tx, "apikey.token", target=audit.Target("apikey", caller.key_id))
    return _out(pair)


@router.post("/refresh")
async def refresh(body: RefreshBody, request: Request) -> TokenOut:
    caller = await key_verify.verify(await request_parts(request), with_token=False)
    return _out(await tokens.refresh(caller.actor, caller.api_key_id, body.refresh_token))


@router.post("/revoke")
async def revoke(body: RevokeBody, request: Request) -> dict[str, str]:
    caller = await key_verify.verify(await request_parts(request), with_token=False)
    await tokens.revoke(caller.actor, caller.api_key_id, body.token)
    return {"status": "revoked"}
