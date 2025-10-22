"""Vector store factory enforcing Chroma backend with fallback stub."""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

try:  # pragma: no cover - prefer real backend
    import chromadb
except ImportError:  # pragma: no cover - fallback
    chromadb = None  # type: ignore


_IN_MEMORY_STORES: Dict[str, Dict[str, Any]] = {}


def _in_memory_collection(name: str) -> Any:
    """Return minimal collection-like object used when chromadb is missing."""

    class _Collection:
        def __init__(self, key: str):
            self._key = key
            _IN_MEMORY_STORES.setdefault(key, {"ids": [], "documents": [], "metadatas": [], "embeddings": []})

        def count(self) -> int:
            return len(_IN_MEMORY_STORES[self._key]["ids"])

        def add(self, ids, documents, metadatas, embeddings):
            store = _IN_MEMORY_STORES[self._key]
            store["ids"].extend(ids)
            store["documents"].extend(documents)
            store["metadatas"].extend(metadatas)
            store["embeddings"].extend(embeddings)

        def get(self, ids=None):
            store = _IN_MEMORY_STORES[self._key]
            if ids is None:
                return store
            results = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
            for idx, stored_id in enumerate(store["ids"]):
                if stored_id in ids:
                    results["ids"].append(stored_id)
                    results["documents"].append(store["documents"][idx])
                    results["metadatas"].append(store["metadatas"][idx])
                    results["embeddings"].append(store["embeddings"][idx])
            return results

    return _Collection(name)


def get_vectorstore(config: Dict[str, Any], exec_meta: Dict[str, Any]) -> Tuple[Any, str]:
    """Return persistent Chroma collection according to configuration."""
    backend = (config.get("vector_backend") or "chroma").lower()
    if backend != "chroma":
        raise AssertionError(f"vector_backend must be 'chroma', got {backend}")

    persist_dir = config.get("persist_dir") or "cache/chroma"
    os.makedirs(persist_dir, exist_ok=True)
    collection_name = config.get("collection_name", "patents")

    if chromadb is None:
        exec_meta.setdefault("warnings", []).append(
            "chromadb package not available; using in-memory vector store."
        )
        collection = _in_memory_collection(f"{persist_dir}:{collection_name}")
    else:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(collection_name)

    exec_meta.setdefault("vector", {})
    exec_meta["vector"].update(
        {"backend": "chroma", "persist_dir": persist_dir, "collection": collection_name}
    )
    return collection, persist_dir


__all__ = ["get_vectorstore"]
