"""BM25 retrieval helpers."""
from __future__ import annotations

from typing import Iterable, List


def build_bm25_index(corpus: Iterable[str]) -> None:
    """Construct a BM25 index from the provided corpus."""
    raise NotImplementedError("BM25 indexing pending implementation.")


def bm25_search(query: str, top_k: int = 8) -> List[str]:
    """Run a BM25 search over the prepared index."""
    raise NotImplementedError("BM25 search logic pending implementation.")
