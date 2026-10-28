"""Remove personal and secret data before anything from a source enters the engine:
the account name, machine name and home folder of whoever runs the server, e-mail
addresses, known token and key formats, long hex/base64 secrets, plus each source's own
patterns (data). Redactions are counted so a reviewer sees that something was removed."""

import getpass
import re
import socket
from dataclasses import dataclass
from pathlib import Path

REDACTED = "[redacted]"
_BUILTIN = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # e-mail
    r"(/Users|/home)/[^/\s]+",  # home folders
    r"\b(zsk|mgk|whsec|whpk|sk|pk|ghp|gho|xox[bap])_[A-Za-z0-9_\-+/=]{8,}",  # tokens
    r"\bAKIA[0-9A-Z]{16}\b",  # cloud access key ids
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    r"\b[0-9a-f]{40,}\b",  # long hex secrets
]


@dataclass(frozen=True, slots=True)
class Clean:
    text: str
    redactions: int


def _local_terms() -> list[str]:
    terms = {getpass.getuser(), str(Path.home())}
    host = socket.gethostname().split(".")[0]
    if len(host) >= 4:  # short host names are ordinary words
        terms.add(host)
    return [re.escape(t) for t in sorted(terms, key=len, reverse=True) if t]


def clean(text: str, extra_patterns: list[str] | None = None) -> Clean:
    """Each pattern is applied on its own (a pattern may carry its own inline flags)."""
    out, count = text, 0
    for pattern in [*_BUILTIN, *_local_terms(), *(extra_patterns or [])]:
        out, n = re.compile(pattern, re.IGNORECASE).subn(REDACTED, out)
        count += n
    return Clean(out, count)


def drop_lines(text: str, line_patterns: list[str]) -> Clean:
    """Remove whole lines that match (e.g. lines naming personal holdings)."""
    if not line_patterns:
        return Clean(text, 0)
    rules = [re.compile(p, re.IGNORECASE) for p in line_patterns]
    kept = [ln for ln in text.splitlines() if not any(r.search(ln) for r in rules)]
    return Clean("\n".join(kept), len(text.splitlines()) - len(kept))
