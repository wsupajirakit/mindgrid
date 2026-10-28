"""Indexing events."""

from mindgrid.platform.events import types


class DocumentIndexed(types.EventData):
    document_id: str
    version_id: str
    chunks: int
    space: str
    links: types.Links


DOCUMENT_INDEXED = types.define(
    "document.indexed",
    "A document version is searchable by meaning (embeddings stored).",
    DocumentIndexed,
)
OUTCOMES = [DOCUMENT_INDEXED.name, "job.failed"]
