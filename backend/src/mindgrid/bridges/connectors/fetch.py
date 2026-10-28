"""Fetch one resource. The target must be https and resolve to a public address, unless
its host is explicitly allowed (internal services); redirects are not followed and the
body is capped, so a connector cannot be turned against the server's own network."""

import base64

import httpx

from mindgrid.core import netguard
from mindgrid.datasets import config as dataset_config

from .spec import Auth, ConnectorSpec, Resource

HTTP_OK = 200


class FetchError(RuntimeError):
    pass


async def check_target(url: str) -> None:
    """Refuse a target the outbound rules do not allow (see core.netguard)."""
    try:
        await netguard.check(url)
    except netguard.BlockedTargetError as err:
        raise FetchError(str(err)) from err


def _auth(auth: Auth, secret: str) -> tuple[dict[str, str], dict[str, str]]:
    """(headers, query) for the auth method."""
    if auth.type == "bearer":
        return {"Authorization": f"Bearer {secret}"}, {}
    if auth.type == "header":
        return {auth.name or "X-Api-Key": secret}, {}
    if auth.type == "query":
        return {}, {auth.name or "api_key": secret}
    if auth.type == "basic":
        return {"Authorization": "Basic " + base64.b64encode(secret.encode()).decode()}, {}
    return {}, {}


async def fetch(spec: ConnectorSpec, resource: Resource, secret: str) -> bytes:
    url = spec.base_url.rstrip("/") + resource.path
    await check_target(url)
    headers, query = _auth(spec.auth, secret)
    limit = dataset_config.get_settings().max_bytes
    params = {**resource.query, **query}
    chunks: list[bytes] = []
    size = 0
    async with (
        httpx.AsyncClient(timeout=spec.timeout_seconds, follow_redirects=False) as client,
        client.stream("GET", url, params=params, headers=headers) as response,
    ):
        if response.status_code != HTTP_OK:
            raise FetchError(f"{resource.path}: HTTP {response.status_code}")
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise FetchError(f"{resource.path}: larger than {limit} bytes")
            chunks.append(chunk)
    return b"".join(chunks)
