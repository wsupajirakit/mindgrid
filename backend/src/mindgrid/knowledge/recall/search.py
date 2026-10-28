"""The three retrievers. Each returns chunk ids best first, already limited to the
project, the requested categories and (through row-level security) what the actor may read.

  vector   cosine distance in one embedding space, through that space's HNSW index
           (iterative scan, so filters do not starve the result)
  keyword  full-text match ('simple' configuration: no stemming, any language)
  trigram  word similarity, for scripts without spaces (Thai) and partial words
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.providers.embeddings.base import Space

from . import config as recall_config


@dataclass(frozen=True, slots=True)
class Scope:
    project_id: uuid.UUID
    category_ids: tuple[uuid.UUID, ...] = ()  # empty = every readable category

    def params(self) -> dict[str, object]:
        return {"project": self.project_id, "cats": list(self.category_ids)}


# Every query filters by project and, when given, by category (bound parameters only).
_HAS_VECTORS = text(
    "select exists (select 1 from chunk_embeddings e where e.space = :space"
    " and e.project_id = :project"
    " and (cardinality(cast(:cats as uuid[])) = 0 or e.category_id = any(cast(:cats as uuid[]))))"
)
_KEYWORD = text(
    "select c.id from chunks c, websearch_to_tsquery('simple', :q) as q"
    " where c.project_id = :project"
    " and (cardinality(cast(:cats as uuid[])) = 0 or c.category_id = any(cast(:cats as uuid[])))"
    " and c.tsv @@ q order by ts_rank_cd(c.tsv, q) desc, c.id limit :n"
)
_TRIGRAM = text(
    "select c.id from chunks c where c.project_id = :project"
    " and (cardinality(cast(:cats as uuid[])) = 0 or c.category_id = any(cast(:cats as uuid[])))"
    " and :q <% c.text order by word_similarity(:q, c.text) desc, c.id limit :n"
)
# The vector size must appear literally so the planner matches the space's index
# expression `(embedding::vector(N))`; N is an integer from the embedding space row.
_VECTOR = (
    "select chunk_id, distance from (select e.chunk_id, (e.embedding::vector({dims}))"
    " <=> cast(cast(:q as text) as vector({dims})) as distance"
    " from chunk_embeddings e where e.space = :space and e.project_id = :project"
    " and (cardinality(cast(:cats as uuid[])) = 0 or e.category_id = any(cast(:cats as uuid[])))"
    " order by distance limit :n) as near order by distance"
)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vector) + "]"


async def has_vectors(tx: AsyncSession, scope: Scope, space: Space) -> bool:
    return bool(await tx.scalar(_HAS_VECTORS, {"space": space.key, **scope.params()}))


async def by_vector(
    tx: AsyncSession, scope: Scope, space: Space, query: list[float]
) -> list[tuple[uuid.UUID, float]]:
    """Nearest chunks with their cosine distance (0 = same direction, 2 = opposite)."""
    cfg = recall_config.get_settings()
    await tx.execute(text("set local hnsw.iterative_scan = relaxed_order"))
    await tx.execute(
        text("select set_config('hnsw.ef_search', :ef, true)"), {"ef": str(cfg.ef_search)}
    )
    statement = text(_VECTOR.format(dims=int(space.dims)))
    params = {"q": vector_literal(query), "space": space.key, "n": cfg.candidates}
    rows = await tx.execute(statement, {**params, **scope.params()})
    return [(r[0], float(r[1])) for r in rows]


async def by_keyword(tx: AsyncSession, scope: Scope, query: str) -> list[uuid.UUID]:
    params = {"q": query, "n": recall_config.get_settings().candidates}
    rows = await tx.execute(_KEYWORD, {**params, **scope.params()})
    return [r[0] for r in rows]


async def by_trigram(tx: AsyncSession, scope: Scope, query: str) -> list[uuid.UUID]:
    cfg = recall_config.get_settings()
    await tx.execute(
        text("select set_config('pg_trgm.word_similarity_threshold', :t, true)"),
        {"t": str(cfg.trigram_threshold)},
    )
    rows = await tx.execute(_TRIGRAM, {"q": query, "n": cfg.candidates, **scope.params()})
    return [r[0] for r in rows]
