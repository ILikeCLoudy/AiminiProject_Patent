"""Hybrid retrieval utilities combining BM25 and Chroma embeddings."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple, Union

from rank_bm25 import BM25Okapi  # type: ignore

from chunks.indexer import generate_embedding, get_collection_records
from retrieval.vectorstore_factory import get_vectorstore

FilterSpec = Union[Dict[str, Any], Callable[[Dict[str, Any]], bool], None]


def _passes_filter(meta: Dict[str, Any], filter_spec: FilterSpec) -> bool:
    if filter_spec is None:
        return True
    if callable(filter_spec):
        return bool(filter_spec(meta))
    for key, expected in filter_spec.items():
        if meta.get(key) != expected:
            return False
    return True


def hybrid_search(
    query: str,
    collection_name: str,
    config: Dict[str, Any],
    exec_meta: Dict[str, Any],
    top_k: int = 8,
    filter: FilterSpec = None,
) -> List[Dict[str, Any]]:
    """Execute hybrid search combining BM25 and vector similarity."""
    records = get_collection_records(config, exec_meta, collection_name)
    filtered_records = [record for record in records if _passes_filter(record["meta"], filter)]
    if not filtered_records:
        exec_meta.setdefault("warnings", []).append(
            f"No records available for collection {collection_name}"
        )
        return []

    token_corpus = [record["text"].lower().split() for record in filtered_records]
    bm25_model = BM25Okapi(token_corpus)
    query_terms = query.lower().split()
    bm25_scores = bm25_model.get_scores(query_terms)
    max_bm25 = float(max(bm25_scores)) if bm25_scores.size else 0.0

    collection, _ = get_vectorstore(config, exec_meta)
    try:
        chroma_results = collection.query(
            query_embeddings=[generate_embedding(query)],
            n_results=top_k,
        )
    except Exception:
        chroma_results = {"ids": [[]], "distances": [[]]}

    embed_scores: Dict[str, float] = {}
    ids = chroma_results.get("ids", [[]])[0] or []
    distances = chroma_results.get("distances", [[]])[0] or []
    for chunk_id, distance in zip(ids, distances):
        if chunk_id is None:
            continue
        record = next((rec for rec in filtered_records if rec["id"] == chunk_id), None)
        if record is None:
            continue
        similarity = max(0.0, 1.0 - float(distance))
        if similarity > embed_scores.get(chunk_id, 0.0):
            embed_scores[chunk_id] = similarity

    alpha = float(config.get("retrieval_alpha", 0.6))
    exec_meta.setdefault("retrieval", {}).update(
        {
            "alpha": alpha,
            "k": top_k,
            "vector_backend": exec_meta.get("vector", {}).get("backend", "chroma"),
        }
    )

    ranked: List[Dict[str, Any]] = []
    for record, bm25_score in zip(filtered_records, bm25_scores):
        doc_id = record["id"]
        bm_norm = float(bm25_score / max_bm25) if max_bm25 else 0.0
        embed_norm = embed_scores.get(doc_id, 0.0)
        score = alpha * bm_norm + (1.0 - alpha) * embed_norm
        if score <= 0:
            continue
        ranked.append(
            {
                "id": doc_id,
                "text": record["text"],
                "meta": record["meta"],
                "score": score,
                "bm25": bm_norm,
                "embedding": embed_norm,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


__all__ = ["hybrid_search"]
