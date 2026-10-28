"""Standard Webhooks signatures and the CloudEvents envelope."""

import base64
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from mindgrid.platform.events import service, signing


def test_v1_hmac_roundtrip_and_tamper() -> None:
    secret = signing.new_secret()
    assert secret.startswith("whsec_")
    body = b'{"a":1}'
    header = signing.hmac_v1(secret, "msg_1", 1700000000, body) + " v1a,abc"
    assert signing.verify_v1(secret, "msg_1", 1700000000, body, header)
    assert not signing.verify_v1(secret, "msg_1", 1700000000, b'{"a":2}', header)
    assert not signing.verify_v1(signing.new_secret(), "msg_1", 1700000000, body, header)


def test_v1a_verifies_with_the_published_key() -> None:
    body = b"{}"
    sig = signing.ed25519_v1a("msg_2", 1700000001, body).removeprefix("v1a,")
    key = signing.public_key()
    raw = base64.b64decode(key["public_key"].removeprefix("whpk_"))
    Ed25519PublicKey.from_public_bytes(raw).verify(base64.b64decode(sig), b"msg_2.1700000001.{}")
    assert key["alg"] == "ed25519"
    assert len(key["key_id"]) == 16


def test_envelope_is_cloudevents() -> None:
    env = service.envelope(
        {
            "event_id": "e1",
            "event_type": "run.completed",
            "project_id": "p1",
            "subject": "runs/r1",
            "event_time": datetime(2026, 10, 25, tzinfo=UTC),
            "data": {"x": 1},
        }
    )
    assert env["specversion"] == "1.0"
    assert env["id"] == "e1"
    assert env["type"] == "run.completed"
    assert env["source"].endswith("/v1/projects/p1")
    assert env["dataschema"].endswith("/v1/events/types/run.completed")
    assert env["time"] == "2026-10-25T00:00:00+00:00"
