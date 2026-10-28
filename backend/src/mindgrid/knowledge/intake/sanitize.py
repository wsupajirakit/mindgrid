"""Text cleaning before anything is stored or embedded. Invisible characters (zero-width,
bidi overrides) are a known way to hide instructions in documents (indirect prompt
injection), so they are removed; control characters too, except newlines and tabs."""

import re
import unicodedata

_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANK_RUN = re.compile(r"\n{3,}")
_SPACE_RUN = re.compile(r"[ \t]{2,}")


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub("", text)
    text = _SPACE_RUN.sub(" ", text)
    return _BLANK_RUN.sub("\n\n", text).strip()
