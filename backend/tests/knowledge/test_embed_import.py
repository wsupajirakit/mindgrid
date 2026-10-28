"""The local embedding library still imports with the pinned image library (fastembed
declares an older one; text embedding does not use it)."""

import importlib


def test_fastembed_text_embedding_imports() -> None:
    module = importlib.import_module("fastembed")
    assert hasattr(module, "TextEmbedding")
