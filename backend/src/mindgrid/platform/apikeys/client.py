"""Client side of the key protocol (CLI, scripts, tests): sign a request with the private
key. The private key never leaves the caller; only signatures travel."""

import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import signing


@dataclass(frozen=True, slots=True)
class KeyCredentials:
    key_id: str
    private_key: Ed25519PrivateKey

    @classmethod
    def from_pem(cls, key_id: str, pem: str) -> KeyCredentials:
        loaded = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(loaded, Ed25519PrivateKey):
            raise ValueError("the private key must be Ed25519")
        return cls(key_id=key_id, private_key=loaded)


@dataclass(frozen=True, slots=True)
class Outgoing:
    """The request to sign, as it will be sent."""

    method: str
    path: str
    query: str = ""
    body: bytes = b""
    token: str = ""


def signed_headers(creds: KeyCredentials, request: Outgoing) -> dict[str, str]:
    """Every header the request needs: Content-Digest, Signature(-Input), Authorization."""
    headers = {"content-digest": signing.content_digest(request.body)}
    if request.token:
        headers["authorization"] = f"Signed {request.token}"
    parts = signing.RequestParts(
        method=request.method,
        path=request.path,
        query=request.query,
        headers=headers,
        body=request.body,
    )
    headers.update(signing.sign(creds.private_key, parts, creds.key_id, int(time.time())))
    return headers
