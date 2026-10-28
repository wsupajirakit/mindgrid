"""Build a proposal from the commits between a source's last learned commit and its head.
Every text that enters the engine is sanitised first; a file is read only when the
mapping wants it."""

from dataclasses import dataclass
from pathlib import Path

from . import config as synapse_config
from . import git, sanitize
from .understand import KNOWLEDGE_KINDS, Item, Mapping, claims, rule_for, touched_functions, wanted


@dataclass(slots=True)
class Built:
    items: list[Item]
    redactions: int = 0


def _clean(mapping: Mapping, text: str) -> sanitize.Clean:
    dropped = sanitize.drop_lines(text, mapping.drop_lines)
    cleaned = sanitize.clean(dropped.text, mapping.redact)
    return sanitize.Clean(cleaned.text, cleaned.redactions + dropped.redactions)


def _file_items(
    repo: Path, change: git.Change, span: tuple[str | None, str], mapping: Mapping, built: Built
) -> list[Item]:
    old, new = span
    rule = rule_for(mapping, change.path)
    if rule.kind == "ignore":
        return []
    raw_patch = git.patch(repo, old, new, change.path)
    diff = _clean(mapping, raw_patch[:20_000])
    built.redactions += diff.redactions
    items = [
        Item("measure", change.path, claim, {"source": "added lines"})
        for claim in claims(diff.text)
    ]
    if rule.kind in KNOWLEDGE_KINDS:
        if change.status == "D":
            return [*items, Item("knowledge_remove", change.path, "removed at the source", {})]
        body = git.content(repo, new, change.path)
        if body is None:
            return items
        clean = _clean(mapping, body)
        built.redactions += clean.redactions
        return [
            *items,
            Item(
                "knowledge_update",
                change.path,
                f"{rule.kind} ({change.status})",
                {"kind": rule.kind, "text": clean.text, "diff": diff.text[:4000]},
            ),
        ]
    fns = touched_functions(raw_patch)
    return [
        *items,
        Item(
            "code_task",
            change.path,
            f"code changed ({change.status})",
            {"target": rule.target, "functions": fns, "diff": diff.text[:6000]},
        ),
    ]


def build(repo: Path, old: str | None, new: str, mapping: Mapping) -> Built:
    """Knowledge and code items first, measurement items after, up to the item limit."""
    built = Built(items=[])
    for change in git.changes(repo, old, new):
        if wanted(mapping, change.path):
            built.items += _file_items(repo, change, (old, new), mapping, built)
    limit = synapse_config.get_settings().max_items
    built.items = sorted(built.items, key=lambda i: i.kind == "measure")[:limit]
    return built
