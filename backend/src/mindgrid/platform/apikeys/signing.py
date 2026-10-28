"""RFC 9421 HTTP Message Signatures profile used by every machine request.

Covered components: "@method" "@path" "@query" "content-digest", plus "authorization"
when a token is sent (binds the token to the request). Parameters: created, nonce,
keyid, alg="ed25519". The body is bound by Content-Digest (RFC 9530, sha-256). One
label, "sig1". Both sides use this module: clients to sign, the server to verify.
"""

import base64
import hashlib
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import sfv

LABEL = "sig1"
ALG = "ed25519"
BASE_COMPONENTS = ("@method", "@path", "@query", "content-digest")
TOKEN_COMPONENTS = (*BASE_COMPONENTS, "authorization")
_SAFE = re.compile(r"^[A-Za-z0-9_.-]{8,64}$")


class SignatureError(Exception):
    """The request's signature is missing, malformed or does not verify."""


@dataclass(frozen=True, slots=True)
class RequestParts:
    method: str
    path: str
    query: str  # without the leading "?"
    headers: Mapping[str, str]  # lower-case names
    body: bytes


@dataclass(frozen=True, slots=True)
class Verified:
    keyid: str
    created: int
    nonce: str
    components: tuple[str, ...]


def content_digest(body: bytes) -> str:
    return f"sha-256=:{base64.b64encode(hashlib.sha256(body).digest()).decode()}:"


def _value(parts: RequestParts, component: str) -> str:
    if component == "@method":
        return parts.method.upper()
    if component == "@path":
        return parts.path
    if component == "@query":
        return f"?{parts.query}"
    value = parts.headers.get(component)
    if value is None:
        raise SignatureError(f"signed header missing: {component}")
    return value.strip()


def signature_base(parts: RequestParts, components: tuple[str, ...], params: str) -> bytes:
    lines = [f'"{c}": {_value(parts, c)}' for c in components]
    lines.append(f'"@signature-params": {params}')
    return "\n".join(lines).encode()


def params_value(components: tuple[str, ...], created: int, nonce: str, keyid: str) -> str:
    if not (_SAFE.fullmatch(nonce) and _SAFE.fullmatch(keyid)):
        raise SignatureError("nonce and keyid must be 8-64 of A-Z a-z 0-9 _ . -")
    listed = " ".join(f'"{c}"' for c in components)
    return f'({listed});created={created};nonce="{nonce}";keyid="{keyid}";alg="{ALG}"'


def sign(key: Ed25519PrivateKey, parts: RequestParts, keyid: str, created: int) -> dict[str, str]:
    """Headers to add to a request (Content-Digest must already be in parts.headers)."""
    components = TOKEN_COMPONENTS if "authorization" in parts.headers else BASE_COMPONENTS
    params = params_value(components, created, secrets.token_urlsafe(18), keyid)
    signature = key.sign(signature_base(parts, components, params))
    return {
        "signature-input": f"{LABEL}={params}",
        "signature": f"{LABEL}=:{base64.b64encode(signature).decode()}:",
    }


def _parse(parts: RequestParts) -> tuple[tuple[str, ...], dict[str, object], str, bytes]:
    try:
        inner, serialized = sfv.inner_list(parts.headers.get("signature-input", ""), LABEL)
        value = sfv.byte_sequence(parts.headers.get("signature", ""), LABEL)
    except sfv.FieldError as err:
        raise SignatureError("missing or malformed Signature / Signature-Input") from err
    return inner.items, inner.params, serialized, value


def verify(parts: RequestParts, public_key: bytes, *, now: int, skew_s: int) -> Verified:
    components, params, serialized, signature = _parse(parts)
    expected = TOKEN_COMPONENTS if "authorization" in parts.headers else BASE_COMPONENTS
    if components != expected or params.get("alg") != ALG:
        raise SignatureError("signature does not cover the required components")
    if parts.headers.get("content-digest") != content_digest(parts.body):
        raise SignatureError("content digest does not match the body")
    created, nonce, keyid = params.get("created"), params.get("nonce"), params.get("keyid")
    if not (isinstance(created, int) and isinstance(nonce, str) and isinstance(keyid, str)):
        raise SignatureError("created, nonce and keyid are required")
    if abs(now - created) > skew_s:
        raise SignatureError("signature timestamp outside the allowed window")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, signature_base(parts, components, serialized)
        )
    except (InvalidSignature, ValueError) as err:
        raise SignatureError("signature does not verify") from err
    return Verified(keyid=keyid, created=created, nonce=nonce, components=components)


def keyid_of(headers: Mapping[str, str]) -> str:
    """The keyid named in Signature-Input (before verification, to find the public key)."""
    try:
        inner, _ = sfv.inner_list(headers.get("signature-input", ""), LABEL)
    except sfv.FieldError as err:
        raise SignatureError("missing or malformed Signature-Input") from err
    keyid = inner.params.get("keyid")
    if not isinstance(keyid, str):
        raise SignatureError("keyid is required")
    return keyid
