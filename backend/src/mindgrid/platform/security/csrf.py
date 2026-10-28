"""CSRF for cookie sessions (OWASP CSRF Prevention: signed double-submit + Fetch Metadata
+ Origin). The CSRF cookie holds HMAC(secret, session token), readable by the web app,
which echoes it in the X-CSRF-Token header on every state-changing request. A Bearer
token is never attached by a browser on its own, so it needs no CSRF token."""

import base64
import hashlib
import hmac
from collections.abc import Mapping

from . import config as security_config

HEADER = "x-csrf-token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BLOCKED_SITES = frozenset({"cross-site", "same-site"})


def token_for(session_token: str) -> str:
    key = hashlib.sha256(b"csrf|" + security_config.secret_bytes()).digest()
    mac = hmac.new(key, session_token.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def failure(method: str, headers: Mapping[str, str], session_token: str) -> str | None:
    """Why a cookie-authenticated request must be refused, or None when it may pass."""
    if method not in UNSAFE_METHODS:
        return None
    if headers.get("sec-fetch-site", "") in _BLOCKED_SITES:
        return "cross-site request refused"
    origin = headers.get("origin")
    if origin and origin.split("://", 1)[-1].rstrip("/") != headers.get("host", ""):
        return "origin does not match"
    supplied = headers.get(HEADER, "")
    if not supplied or not hmac.compare_digest(supplied, token_for(session_token)):
        return "missing or invalid CSRF token"
    return None
