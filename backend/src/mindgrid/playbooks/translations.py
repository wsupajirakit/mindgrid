"""Translated playbook titles and summaries: the text a spec ships, overridden by what a
superadmin saved (stored per playbook and language)."""

import re
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from .models import PlaybookTranslation
from .spec import LOCALE, PlaybookSpec, Translation

Texts = dict[str, dict[str, Translation]]  # playbook id -> locale -> text


def shipped(specs: dict[tuple[str, int], PlaybookSpec]) -> Texts:
    """Each playbook's translations as its newest version ships them."""
    newest: dict[str, PlaybookSpec] = {}
    for (pid, version), spec in specs.items():
        if pid not in newest or version > newest[pid].version:
            newest[pid] = spec
    return {pid: dict(spec.translations) for pid, spec in newest.items()}


async def merged(tx: AsyncSession, specs: dict[tuple[str, int], PlaybookSpec]) -> Texts:
    out = shipped(specs)
    for row in (await tx.scalars(select(PlaybookTranslation))).all():
        out.setdefault(row.playbook_id, {})[row.locale] = Translation(
            title=row.title, summary=row.summary
        )
    return out


def _check(locale: str) -> None:
    if not re.fullmatch(LOCALE, locale) or locale == "en":
        raise ApiError(400, "playbook.bad_locale", "a two-letter language other than en")


async def put(
    tx: AsyncSession,
    specs: dict[tuple[str, int], PlaybookSpec],
    target: tuple[str, str],
    text: Translation,
) -> None:
    """Save `text` for (playbook id, locale); `specs` is the catalog it must belong to."""
    playbook_id, locale = target
    _check(locale)
    if not any(pid == playbook_id for pid, _ in specs):
        raise ApiError(404, "playbook.not_found", "playbook not found")
    stmt = insert(PlaybookTranslation).values(
        playbook_id=playbook_id, locale=locale, title=text.title, summary=text.summary
    )
    await tx.execute(
        stmt.on_conflict_do_update(
            index_elements=["playbook_id", "locale"],
            set_={"title": text.title, "summary": text.summary, "updated_at": datetime.now(UTC)},
        )
    )
    await audit.record(
        tx,
        "playbook.translate",
        target=audit.Target("playbook", playbook_id),
        details={"locale": locale},
    )


async def clear(tx: AsyncSession, playbook_id: str, locale: str) -> None:
    """Back to the text the spec ships (if any)."""
    _check(locale)
    await tx.execute(
        delete(PlaybookTranslation).where(
            PlaybookTranslation.playbook_id == playbook_id, PlaybookTranslation.locale == locale
        )
    )
