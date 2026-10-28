"""The narrative rule of tools/check_notes.py: request narrative fails, technical nouns pass."""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[3] / "tools" / "check_notes.py"
_SPEC = importlib.util.spec_from_file_location("check_notes", _PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
check_notes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_notes)


@pytest.mark.parametrize(
    ("text", "narrative"),
    [
        ("the user decided to use X", True),
        ("User wants dark mode", True),
        ("per the owner", True),
        ("requested by the team", True),
        ("runs as the owner role", False),
        ("needs the user row", False),
        ("with the owner's rights", False),
        ("one download per user gesture", False),
    ],
)
def test_narrative_rule(text: str, narrative: bool) -> None:
    assert bool(check_notes.NARRATIVE.search(text)) is narrative
