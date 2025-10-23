"""Evidence retrieval for TRL and claims analysis."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Tuple

from chunks.indexer import get_collection_records
from retrieval.hybrid import hybrid_search

TRL_CUES = [
    "prototype",
    "pilot",
    "field test",
    "operational environment",
    "relevant environment",
    "production",
    "deployed",
    "on-device",
    "real-time",
    "proof-of-concept",
    "simulation only",
    "flight",
]

CLAIM_CUES = ["comprising", "wherein", "at least one", "configured to"]

TRL_RULES: List[Tuple[Tuple[str, ...], float]] = [
    (("deployed", "production"), 8.5),
    (("operational environment", "flight"), 8.0),
    (("relevant environment", "field test"), 6.5),
    (("pilot",), 7.0),
    (("prototype",), 5.5),
    (("proof-of-concept", "simulation only"), 4.0),
]


def _normalize_snippets(snippets: List[Dict[str, Any]], max_snippets: int) -> List[Dict[str, Any]]:
    ranked = sorted(snippets, key=lambda item: item.get("score", 0.0), reverse=True)
    return ranked[:max_snippets]


def _score_trl_snippet(snippet_text: str) -> float:
    lowered = snippet_text.lower()
    best_score = 0.0
    for cues, level in TRL_RULES:
        if all(cue in lowered for cue in cues):
            best_score = max(best_score, level)
    return best_score


def _build_evidence_entries(
    metric: str,
    snippets: List[Dict[str, Any]],
    exec_meta: Dict[str, Any],
    badge: str = "Local RAG",
    max_chars: int = 900,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    retrieval_ts = exec_meta.get("ts")
    for snippet in snippets:
        meta = dict(snippet.get("meta", {}))
        text = snippet.get("text", "")
        if max_chars and len(text) > max_chars:
            text = text[: max(0, max_chars - 3)].rstrip() + "..."
        checksum = "sha256:" + hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        doc_ref = meta.get("doc_ref") or meta.get("source_path")
        entry = {
            "metric": metric,
            "text": text,
            "badge": badge,
            "source_type": meta.get("source_type", "PDF"),
            "source": meta.get("source", meta.get("doc_id", "")),
            "source_id": meta.get("source_id", meta.get("doc_id", "")),
            "doc_ref": doc_ref,
            "text_checksum": checksum,
            "offsets": meta.get("offsets", {}),
            "retrieval_ts": retrieval_ts,
            "fetch_ts": retrieval_ts,
            "cache_info": {"hit": False},
            "budget_used": 0,
            "retries": 0,
            "status": "ok",
            "error": None,
            "score_trace": {
                "hybrid": snippet.get("score"),
                "bm25": snippet.get("bm25"),
                "embedding": snippet.get("embedding"),
                "cue": snippet.get("cue"),
            },
        }
        entries.append(entry)
    return entries


def _aggregate_hits(
    cues: Iterable[str],
    collection: str,
    config: Dict[str, Any],
    exec_meta: Dict[str, Any],
    k_per_query: int,
    filter_meta: Dict[str, Any] | None = None,
    allowed_docs: Iterable[str] | None = None,
) -> List[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    allowed = {doc.lower() for doc in (allowed_docs or []) if isinstance(doc, str)}
    for cue in cues:
        hits = hybrid_search(cue, collection, config, exec_meta, top_k=k_per_query, filter=filter_meta)
        for hit in hits:
            merged = {**hit, "cue": cue}
            doc_id = merged.get("meta", {}).get("doc_id")
            if allowed and doc_id and doc_id.lower() not in allowed:
                continue
            existing = aggregated.get(merged["id"])
            if existing is None or merged["score"] > existing["score"]:
                aggregated[merged["id"]] = merged
    return list(aggregated.values())


def _infer_trl_level(snippets: List[Dict[str, Any]]) -> float | None:
    scores: List[Tuple[float, Dict[str, Any]]] = []
    for snippet in snippets:
        level = _score_trl_snippet(snippet["text"])
        if level > 0:
            scores.append((level, snippet))
    if not scores:
        return None
    scores.sort(key=lambda item: (item[0], item[1].get("score", 0.0)), reverse=True)
    return scores[0][0]


def _summarize_claim_patterns(records: List[Dict[str, Any]]) -> Dict[str, int]:
    pattern_stats: Dict[str, int] = {}
    for cue in CLAIM_CUES:
        count = sum(record["text"].lower().count(cue) for record in records)
        pattern_stats[cue] = count
    return pattern_stats


def gather_trl_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    """Collect TRL-related snippets using local RAG."""
    config = state.get("config", {})
    exec_meta = state.setdefault("exec_meta", {})
    patents_collection = (
        state.get("index", {}).get("patents_index") or config.get("collection_name", "patents")
    )
    trl_collection = state.get("index", {}).get("trl_ref_index") or "trl_ref"
    if not patents_collection:
        return {"ok": False, "warnings": ["Patents index missing."], "updates": {}}

    alpha = config.get("retrieval_alpha", 0.6)
    k_per_query = config.get("k_per_query", 6)
    max_snippets = config.get("max_snippets_per_metric", 3)
    max_chars = int(config.get("max_snippet_chars", 900))
    allowed_docs = {meta.get("doc_id", "").lower() for meta in state.get("inputs", {}).get("metas", []) if meta.get("doc_id")}
    if allowed_docs:
        allowed_docs.add("swtrls")
        allowed_iter = allowed_docs
    else:
        allowed_iter = None

    snippets = _aggregate_hits(
        TRL_CUES,
        patents_collection,
        config,
        exec_meta,
        k_per_query,
        allowed_docs=allowed_iter,
    )
    snippets = _normalize_snippets(snippets, max_snippets)

    # Get keyword-based TRL estimate
    keyword_level = _infer_trl_level(snippets)

    # Try LLM Tool Calling for enhanced evaluation
    trl_eval = {"trl_level": keyword_level, "source": "keyword_matching"}
    if config.get("llm", {}).get("use_tool_calling", False):
        try:
            from llm.tool_calling import evaluate_trl_with_llm
            trl_eval = evaluate_trl_with_llm(snippets, keyword_level, config)
            exec_meta.setdefault("logs", []).append(
                f"TRL: LLM tool calling used (confidence={trl_eval.get('confidence', 0):.2f})"
            )
        except Exception as e:
            exec_meta.setdefault("warnings", []).append(f"TRL tool calling failed: {str(e)}")
            trl_eval = {"trl_level": keyword_level, "source": "keyword_matching_fallback"}

    level = trl_eval.get("trl_level")
    evidence_entries = _build_evidence_entries("trl", snippets, exec_meta, badge="Local RAG", max_chars=max_chars)

    ref_snippets: List[Dict[str, Any]] = []
    if trl_collection and level:
        query = f"TRL {level}"
        ref_snippets = hybrid_search(query, trl_collection, config, exec_meta, top_k=max_snippets)
        if not ref_snippets:
            ref_snippets = hybrid_search("TRL definition", trl_collection, config, exec_meta, top_k=max_snippets)
    ref_entries = _build_evidence_entries("trl_ref", ref_snippets, exec_meta, badge="Local RAG")

    evidence_payload = {
        "trl_level_est": level,
        "evidence_snippets": evidence_entries,
        "ref_snippets": ref_entries,
        "source_badge": "Local RAG",
    }

    state.setdefault("evidence", {}).setdefault("trl", {}).update(
        {
            "level": level,
            "snippets": evidence_entries,
            "ref_snippets": ref_entries,
            "source_badge": "Local RAG",
            "evaluation_method": trl_eval.get("source", "keyword_matching"),
            "confidence": trl_eval.get("confidence"),
            "reasoning": trl_eval.get("reasoning"),
            "key_indicators": trl_eval.get("key_indicators", []),
            "fallback_score": trl_eval.get("fallback_score"),
        }
    )

    if evidence_entries:
        provenance = state.setdefault("provenance", {})
        provenance.setdefault("evidence", []).append(
            {
                "metric": "trl",
                "checksums": [entry["text_checksum"] for entry in evidence_entries],
                "badge": "Local RAG",
            }
        )

    scores = state.setdefault("scores", {})
    scores["trl"] = float(min(100.0, max(0.0, level * 10.0))) if level is not None else None

    retrieval_meta = state.setdefault("exec_meta", {}).setdefault("retrieval", {})
    retrieval_meta["alpha"] = alpha
    retrieval_meta["trl_k_per_query"] = k_per_query
    retrieval_meta["max_snippets_per_metric"] = max_snippets
    retrieval_meta["trl_snippets"] = len(snippets)
    retrieval_meta["trl_ref_snippets"] = len(ref_snippets)

    return {"ok": True, "updates": {("evidence", "trl"): state["evidence"]["trl"]}}


def gather_claims_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    """Collect claims-related snippets using local RAG."""
    config = state.get("config", {})
    patents_collection = state.get("index", {}).get("patents_index") or state.get("config", {}).get("collection_name", "patents")
    if not patents_collection:
        return {"ok": False, "warnings": ["Patents index missing."], "updates": {}}

    alpha = config.get("retrieval_alpha", 0.6)
    k_per_query = config.get("k_per_query", 6)
    max_snippets = config.get("max_snippets_per_metric", 3)

    exec_meta = state.setdefault("exec_meta", {})
    max_chars = int(config.get("max_snippet_chars", 900))
    allowed_docs = {meta.get("doc_id", "").lower() for meta in state.get("inputs", {}).get("metas", []) if meta.get("doc_id")}
    if allowed_docs:
        allowed_docs.add("swtrls")
        allowed_iter = allowed_docs
    else:
        allowed_iter = None
    snippets = _aggregate_hits(
        CLAIM_CUES,
        patents_collection,
        config,
        exec_meta,
        k_per_query,
        {"section": "claims"},
        allowed_docs=allowed_iter,
    )
    snippets = _normalize_snippets(snippets, max_snippets)
    claim_entries = _build_evidence_entries("claims", snippets, exec_meta, badge="Local RAG", max_chars=max_chars)

    all_records = get_collection_records(config, exec_meta, patents_collection)
    claim_records = [record for record in all_records if record["meta"].get("section") == "claims"]
    independent_map: Dict[Any, List[str]] = {}
    for record in claim_records:
        if record["meta"].get("independent") and record["meta"].get("claim_id") is not None:
            claim_key = record["meta"]["claim_id"]
            independent_map.setdefault(claim_key, []).append(record["text"])

    num_independent = len(independent_map)
    avg_len_tokens = (
        float(
            sum(len(" ".join(texts).split()) for texts in independent_map.values()) / max(num_independent, 1)
        )
        if num_independent
        else 0.0
    )
    pattern_stats = _summarize_claim_patterns(claim_records)

    # Try LLM Tool Calling for claim quality evaluation
    from scoring.scoring import compute_claim_score
    baseline_score = compute_claim_score(num_independent, avg_len_tokens)

    claim_eval = {"quality_score": baseline_score, "source": "formula"}
    if config.get("llm", {}).get("use_tool_calling", False) and num_independent > 0:
        try:
            from llm.tool_calling import evaluate_claims_with_llm
            claim_eval = evaluate_claims_with_llm(
                num_independent, avg_len_tokens, snippets, baseline_score, config
            )
            exec_meta.setdefault("logs", []).append(
                f"Claims: LLM tool calling used (confidence={claim_eval.get('confidence', 0):.2f})"
            )
        except Exception as e:
            exec_meta.setdefault("warnings", []).append(f"Claims tool calling failed: {str(e)}")
            claim_eval = {"quality_score": baseline_score, "source": "formula_fallback"}

    state.setdefault("evidence", {}).setdefault("claims", {}).update(
        {
            "num_independent": num_independent,
            "avg_len_tokens": avg_len_tokens,
            "pattern_stats": pattern_stats,
            "snippets": claim_entries,
            "source_badge": "Local RAG",
            "evaluation_method": claim_eval.get("source", "formula"),
            "quality_score": claim_eval.get("quality_score"),
            "breadth_assessment": claim_eval.get("breadth_assessment"),
            "confidence": claim_eval.get("confidence"),
            "reasoning": claim_eval.get("reasoning"),
            "strengths": claim_eval.get("strengths", []),
            "weaknesses": claim_eval.get("weaknesses", []),
            "fallback_score": claim_eval.get("fallback_score"),
        }
    )

    if claim_entries:
        provenance = state.setdefault("provenance", {})
        provenance.setdefault("evidence", []).append(
            {
                "metric": "claims",
                "checksums": [entry["text_checksum"] for entry in claim_entries],
                "badge": "Local RAG",
            }
        )

    retrieval_meta = state.setdefault("exec_meta", {}).setdefault("retrieval", {})
    retrieval_meta["claims_k_per_query"] = k_per_query
    retrieval_meta["claims_alpha"] = alpha
    retrieval_meta["max_snippets_per_metric"] = max_snippets
    retrieval_meta["claims_snippets"] = len(snippets)

    return {"ok": True, "updates": {("evidence", "claims"): state["evidence"]["claims"]}}


__all__ = [
    "gather_trl_evidence",
    "gather_claims_evidence",
    "TRL_CUES",
    "CLAIM_CUES",
    "TRL_RULES",
    "_score_trl_snippet",
    "_summarize_claim_patterns",
]

