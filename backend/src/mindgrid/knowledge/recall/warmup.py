"""Load the local models before the first question (in the background, so start-up is not
delayed): the first recall would otherwise wait for both models to load."""

import structlog

from mindgrid.core import runtime
from mindgrid.providers import config as provider_config
from mindgrid.providers.embeddings import factory as embed_factory
from mindgrid.providers.rerank import factory as rerank_factory

log = structlog.get_logger(__name__)


async def warm() -> None:
    if runtime.get_settings().environment == "test":
        return
    try:
        if provider_config.get_settings().provider == "local":
            await embed_factory.build().embed_query("warm up")
        reranker = rerank_factory.build()
        if reranker is not None:
            await reranker.score("warm up", ["warm up"])
        log.info("models.warm")
    except Exception as err:  # a missing model only slows the first question
        log.warning("models.warm_failed", error=repr(err))
