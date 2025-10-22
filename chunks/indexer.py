"""Chunk indexing utilities with Chroma persistence and fingerprinting."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional

from retrieval.vectorstore_factory import get_vectorstore

_EMBED_DIM = 384


def _normalize_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _build_fingerprint(text: str, meta: Dict[str, Any]) -> str:
    normalized = _normalize_text(text)
    meta_key = json.dumps(meta, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(f"{normalized}|{meta_key}".encode("utf-8")).hexdigest()
    return digest[:16]


def _deterministic_embedding(text: str, dimension: int = _EMBED_DIM) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    data = bytearray(digest)
    while len(data) < dimension * 4:
        data.extend(hashlib.sha256(data).digest())
    vec: List[float] = []
    for i in range(dimension):
        start = i * 4
        chunk = data[start : start + 4]
        value = int.from_bytes(chunk, "little", signed=False)
        vec.append((value % 2000) / 1000.0 - 1.0)
    return vec


def upsert_chunks(
    chunks: List[Dict[str, Any]],
    collection_name: str,
    *,
    config: Optional[Dict[str, Any]] = None,
    exec_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Upsert chunk documents into Chroma vector store and return counts."""
    config = config or {}
    if exec_meta is None:
        exec_meta = {}

    collection, _ = get_vectorstore(config, exec_meta)

    snapshot = collection.get() if collection.count() > 0 else {"ids": []}
    existing_ids = set(snapshot.get("ids", []))
    embedded = exec_meta.setdefault("embedding", {}).get("embedded", 0)
    skipped = exec_meta.setdefault("embedding", {}).get("skipped", 0)
    snippets = exec_meta["embedding"].setdefault("snippets", 0)
    tokens_est = exec_meta["embedding"].setdefault("tokens_est", 0)
    cap = exec_meta["embedding"].setdefault("cap", config.get("embedding_token_cap_per_run", 25000))

    ids: List[str] = []
    texts: List[str] = []
    metas: List[Dict[str, Any]] = []
    embeddings: List[List[float]] = []

    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        meta = dict(chunk.get("meta", {}))
        fingerprint = _build_fingerprint(text, meta)
        meta["fingerprint"] = fingerprint

        if meta.get("no_embed") or meta.get("meta_only"):
            exec_meta["embedding"]["meta_skipped"] = exec_meta["embedding"].get("meta_skipped", 0) + 1
            skipped += 1
            continue

        if chunk_id in existing_ids:
            skipped += 1
            continue

        ids.append(chunk_id)
        texts.append(text)
        metas.append(meta)
        embeddings.append(_deterministic_embedding(text))

        token_estimate = max(len(text.split()), 1)
        tokens_est += token_estimate
        snippets += 1

    if ids:
        collection.add(ids=ids, documents=texts, metadatas=metas, embeddings=embeddings)
        embedded += len(ids)

    exec_meta["embedding"].update(
        {
            "embedded": embedded,
            "skipped": skipped,
            "snippets": snippets,
            "tokens_est": tokens_est,
            "cap": cap,
        }
    )
    return {"count": len(ids), "skipped": skipped}


__all__ = ["upsert_chunks", "get_collection_records", "generate_embedding", "cosine_similarity"]



def get_collection_records(config_or_name, exec_meta: Optional[Dict[str, Any]] = None, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return collection records as dictionaries (testing helper)."""
    if isinstance(config_or_name, dict):
        config = config_or_name
        exec_meta = exec_meta or {}
        name = collection_name or config.get("collection_name", "patents")
    else:
        config = {}
        exec_meta = exec_meta or {}
        name = config_or_name
    collection, _ = get_vectorstore(config, exec_meta)
    snapshot = collection.get()
    records: List[Dict[str, Any]] = []
    ids = snapshot.get("ids", [])
    documents = snapshot.get("documents", [])
    metadatas = snapshot.get("metadatas", [])
    embeddings = snapshot.get("embeddings", [])
    tokens_list = snapshot.get("tokens", embeddings)
    for idx, chunk_id in enumerate(ids):
        text = documents[idx]
        meta = metadatas[idx] if idx < len(metadatas) else {}
        embedding = embeddings[idx] if idx < len(embeddings) else []
        tokens = text.lower().split()
        record = {
            "id": chunk_id,
            "text": text,
            "meta": meta,
            "embedding": embedding,
            "tokens": tokens,
        }
        records.append(record)
    return records


def generate_embedding(text: str, dimension: int = _EMBED_DIM) -> List[float]:
    """Expose deterministic embedding for consumers (until real backend wired)."""
    return _deterministic_embedding(text, dimension)


def cosine_similarity(vec_a: Iterable[float], vec_b: Iterable[float]) -> float:
    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        mag_a += a * a
        mag_b += b * b
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a ** 0.5 * mag_b ** 0.5)

