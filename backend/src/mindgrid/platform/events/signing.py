"""Standard Webhooks signatures. `v1`: HMAC-SHA256 with the subscription secret
(`whsec_` + base64); `v1a`: Ed25519 with the server's event key, derived from the server
secret (its public half is published, so callbacks need no shared secret). Both sign
`<webhook-id>.<webhook-timestamp>.<body>`; the header carries every signature, space
separated."""

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from mindgrid.platform.security import config as security_config

SECRET_PREFIX = "whsec_"  # noqa: S105 — the format prefix, not a secret
SECRET_BYTES = 32


def new_secret() -> str:
    return SECRET_PREFIX + base64.b64encode(os.urandom(SECRET_BYTES)).decode()


def _content(msg_id: str, timestamp: int, body: bytes) -> bytes:
    return f"{msg_id}.{timestamp}.".encode() + body


def hmac_v1(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    key = base64.b64decode(secret.removeprefix(SECRET_PREFIX))
    digest = hmac.new(key, _content(msg_id, timestamp, body), hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def _server_key() -> Ed25519PrivateKey:
    seed = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"mindgrid/events", info=b"events-ed25519-v1"
    ).derive(security_config.secret_bytes())
    return Ed25519PrivateKey.from_private_bytes(seed)


def ed25519_v1a(msg_id: str, timestamp: int, body: bytes) -> str:
    signature = _server_key().sign(_content(msg_id, timestamp, body))
    return "v1a," + base64.b64encode(signature).decode()


def public_key() -> dict[str, str]:
    """The server's event key, published for receivers (`whpk_` + base64 raw key)."""
    raw = (
        _server_key()
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )
    key_id = hashlib.sha256(raw).hexdigest()[:16]
    return {
        "key_id": key_id,
        "alg": "ed25519",
        "public_key": "whpk_" + base64.b64encode(raw).decode(),
    }


def verify_v1(secret: str, msg_id: str, timestamp: int, body: bytes, header: str) -> bool:
    """For receivers and tests: does `header` hold a valid v1 signature?"""
    want = hmac_v1(secret, msg_id, timestamp, body)
    return any(hmac.compare_digest(want, part) for part in header.split())
