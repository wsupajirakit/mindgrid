"""The RFC 9421 profile: what is covered, the ±window, malformed input."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mindgrid.platform.apikeys import signing

KEY = Ed25519PrivateKey.generate()
PUBLIC = KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
NOW = 1_800_000_000


def _signed(
    path: str = "/v1/projects", query: str = "", body: bytes = b"", created: int = NOW
) -> signing.RequestParts:
    headers = {"content-digest": signing.content_digest(body), "authorization": "Signed tok"}
    parts = signing.RequestParts("GET", path, query, headers, body)
    headers.update(signing.sign(KEY, parts, "mgk_testkey01", created))
    return parts


def test_window_is_inclusive_of_the_skew() -> None:
    parts = _signed(created=NOW - 300)
    assert signing.verify(parts, PUBLIC, now=NOW, skew_s=300).keyid == "mgk_testkey01"
    with pytest.raises(signing.SignatureError, match="window"):
        signing.verify(_signed(created=NOW + 301), PUBLIC, now=NOW, skew_s=300)


@pytest.mark.parametrize("change", ["path", "query", "token"])
def test_every_covered_part_is_bound(change: str) -> None:
    parts = _signed(query="a=1")
    headers = dict(parts.headers)
    if change == "token":
        headers["authorization"] = "Signed other"
    moved = signing.RequestParts(
        parts.method,
        "/v1/other" if change == "path" else parts.path,
        "a=2" if change == "query" else parts.query,
        headers,
        parts.body,
    )
    with pytest.raises(signing.SignatureError):
        signing.verify(moved, PUBLIC, now=NOW, skew_s=300)


def test_malformed_headers_are_refused() -> None:
    bad = signing.RequestParts(
        "GET", "/", "", {"signature-input": "nonsense", "signature": "x"}, b""
    )
    with pytest.raises(signing.SignatureError):
        signing.verify(bad, PUBLIC, now=NOW, skew_s=300)
