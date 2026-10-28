"""AES-256-GCM sealing. The key comes from MINDGRID_SECRET_KEY through HKDF-SHA256 with
its own label (separate from the CSRF key); every value has a random 96-bit nonce and is
bound to where it is stored (associated data), so a ciphertext copied to another row or
project does not open. `version` names the derivation, for a future key rotation."""

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from mindgrid.platform.security import config as security_config

CURRENT_VERSION = 1
NONCE_BYTES = 12


@dataclass(frozen=True, slots=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    version: int


def _key(version: int) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"mindgrid/secrets",
        info=f"secrets-v{version}".encode(),
    )
    return hkdf.derive(security_config.secret_bytes())


def seal(plaintext: str, binding: str) -> Sealed:
    nonce = os.urandom(NONCE_BYTES)
    data = AESGCM(_key(CURRENT_VERSION)).encrypt(nonce, plaintext.encode(), binding.encode())
    return Sealed(ciphertext=data, nonce=nonce, version=CURRENT_VERSION)


def open_sealed(sealed: Sealed, binding: str) -> str:
    """Decrypt; raises cryptography.exceptions.InvalidTag on tampering or a wrong binding."""
    plain = AESGCM(_key(sealed.version)).decrypt(sealed.nonce, sealed.ciphertext, binding.encode())
    return plain.decode()
