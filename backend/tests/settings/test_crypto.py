"""Sealing: round trip, random nonces, and a value bound to where it is stored."""

import pytest
from cryptography.exceptions import InvalidTag

from mindgrid.platform.secrets import crypto


def test_round_trip_random_nonce_and_binding() -> None:
    first = crypto.seal("api-key-123", "project:p1:gemini")
    second = crypto.seal("api-key-123", "project:p1:gemini")
    assert first.ciphertext != second.ciphertext
    assert b"api-key-123" not in first.ciphertext
    assert crypto.open_sealed(first, "project:p1:gemini") == "api-key-123"
    with pytest.raises(InvalidTag):
        crypto.open_sealed(first, "project:p2:gemini")  # copied to another project


def test_tampering_is_detected() -> None:
    sealed = crypto.seal("value", "system:-:x")
    broken = crypto.Sealed(
        bytes([sealed.ciphertext[0] ^ 1]) + sealed.ciphertext[1:], sealed.nonce, sealed.version
    )
    with pytest.raises(InvalidTag):
        crypto.open_sealed(broken, "system:-:x")
