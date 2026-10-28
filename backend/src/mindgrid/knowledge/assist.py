"""Optional LLM help around retrieval (contextual chunks at indexing, query rewriting,
judging evals). Each step is switched per scope by its own setting: off (default),
gemini (the project's Gemini key) or local (the Ollama server). The same writers as
server-side answers are used, so no step adds a provider of its own."""

import uuid
from typing import Literal, cast

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.settings_registry import Definition, Scope
from mindgrid.platform.secrets import service as secrets
from mindgrid.platform.settings import service as settings_service
from mindgrid.providers.llm import factory
from mindgrid.providers.llm.base import Prompt, Writer, WriterError

Mode = Literal["off", "gemini", "local"]
GEMINI_KEY = "provider.gemini.api_key"


async def mode_of(
    tx: AsyncSession, setting: Definition, project_id: uuid.UUID, category_id: uuid.UUID | None
) -> Mode:
    chain: list[tuple[Scope, uuid.UUID | None]] = []
    if category_id is not None and Scope.CATEGORY in setting.scopes:
        chain.append((Scope.CATEGORY, category_id))
    chain += [(Scope.PROJECT, project_id), (Scope.SYSTEM, None)]
    resolved = await settings_service.resolve(tx, setting.key, chain)
    return cast(Mode, resolved.value)


async def writer_for(tx: AsyncSession, project_id: uuid.UUID, mode: str) -> Writer | None:
    """The writer for a mode (None when off or none). Raises WriterUnavailableError when
    the mode cannot run, e.g. gemini without a stored key."""
    if mode not in ("gemini", "local"):
        return None
    key = ""
    if mode == "gemini":
        key = await secrets.reveal_provider_key(tx, project_id, GEMINI_KEY) or ""
    return factory.build(cast(factory.Mode, mode), gemini_key=key)


async def complete(writer: Writer, prompt: Prompt, seconds: float) -> str:
    """One bounded call: a writer error or the time limit raises WriterError."""
    try:
        with anyio.fail_after(seconds):
            return await writer.write(prompt)
    except TimeoutError as err:
        raise WriterError(f"no reply within {seconds:g} s") from err
