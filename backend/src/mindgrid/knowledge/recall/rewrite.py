"""Optional query rewriting: an LLM turns the question into a search query (exact names
and numbers kept, the terms a matching passage would use added). The rewritten query only
ADDS candidates: both queries are searched and fused, and the reranker still scores every
passage against the original question, so a poor rewrite cannot push out a good passage.
Any failure or time-out skips the step and is named in `skipped`."""

from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.settings_registry import Scope, define
from mindgrid.providers.llm import factory
from mindgrid.providers.llm.base import Prompt, WriterError

from .. import assist
from . import config as recall_config
from .types import Ask, Recall

REWRITE = define(
    "recall.rewrite",
    assist.Mode,
    "off",
    {Scope.SYSTEM, Scope.PROJECT},
    "Rewrite questions into search queries before recall: off, gemini (needs the Gemini key) "
    "or local (an Ollama server). The original question is always searched too.",
)
RULES = (
    "Rewrite the question as one search query for a document index. Keep names, codes, "
    "tickers and numbers exactly as written. Add the key terms and close synonyms that a "
    "passage answering it would use, in the question's language and in English. Reply with "
    "the query only, on one line, at most 40 words."
)


def _one_line(text: str, limit: int) -> str:
    line = " ".join(text.split())
    for prefix in ("query:", "search query:"):
        if line.casefold().startswith(prefix):
            line = line[len(prefix) :].strip()
    return line.strip("\"'` ")[:limit]


async def rewritten(tx: AsyncSession, ask: Ask, query: str, out: Recall) -> str | None:
    mode = await assist.mode_of(tx, REWRITE, ask.project_id, None)
    if mode == "off":
        return None
    try:
        writer = await assist.writer_for(tx, ask.project_id, mode)
    except factory.WriterUnavailableError as err:
        out.skipped["rewrite"] = f"rewriter unavailable: {err}"
        return None
    if writer is None:
        return None
    cfg = recall_config.get_settings()
    try:
        reply = await assist.complete(
            writer, Prompt(RULES, f"Question: {query}"), cfg.rewrite_seconds
        )
    except WriterError as err:
        out.skipped["rewrite"] = f"rewriting failed: {err}"
        return None
    line = _one_line(reply, cfg.max_query_chars)
    if not line or line.casefold() == query.casefold():
        return None
    out.rewritten = line
    return line
