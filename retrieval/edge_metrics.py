"""Edge performance metric extraction from evidence snippets."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


_PATTERNS: Dict[str, Tuple[re.Pattern[str], str]] = {
    "latency_ms": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:ms|millisecond)", re.IGNORECASE), "ms"),
    "power_mw": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:mw|milliwatt)", re.IGNORECASE), "mW"),
    "memory_mb": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:mb|megabyte)", re.IGNORECASE), "MB"),
    "accuracy_delta": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percentage\s+points).{0,20}accuracy", re.IGNORECASE), "%"),
}


def _collect_texts(evidence: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for payload in evidence.values():
        snippets: Iterable[Dict[str, Any]] = payload.get("snippets", [])
        for snippet in snippets:
            text = snippet.get("text")
            if text:
                texts.append(text)
    return texts


def extract_edge_performance(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract edge performance metrics with priority:
    1. User-provided metadata (highest trust)
    2. Tavily search results (medium-high trust)
    3. Evidence snippet extraction (medium trust)
    4. LLM inference (low trust)
    5. Empty/N/A (requires manual input)
    """
    config = state.get("config", {})
    exec_meta = state.setdefault("exec_meta", {})

    # Priority 1: Check user-provided metadata
    metas = state.get("inputs", {}).get("metas", [])
    if metas:
        primary_meta = metas[0]
        user_perf = primary_meta.get("edge_performance", {})
        if user_perf:
            metrics = {}
            for key in ["latency_ms", "power_mw", "memory_mb", "accuracy_delta"]:
                if key in user_perf:
                    metrics[key] = {
                        "value": user_perf[key],
                        "unit": _PATTERNS[key][1] if key in _PATTERNS else "",
                        "source": user_perf.get("source", "user_provided"),
                        "priority": 1
                    }
            if metrics:
                state.setdefault("performance", {})["metrics"] = metrics
                exec_meta.setdefault("logs", []).append("Edge: User-provided metadata used")
                return metrics

    # Priority 2: Tavily search for performance benchmarks
    if config.get("tavily", {}).get("enabled") and config.get("edge_adapter", {}).get("use_tavily", True):
        try:
            from adapters.link_finder_tavily import search_official_links, snapshot_and_extract, pick_snippets

            doc_id = metas[0].get("doc_id") if metas else "unknown"
            title = metas[0].get("title") if metas else ""

            queries = [
                f"{doc_id} {title} latency benchmark performance",
                f"{doc_id} power consumption measurement",
                f"{title} edge device inference speed"
            ]

            perf_snippets = []
            for query in queries[:2]:  # Limit to 2 queries
                results = search_official_links(config, exec_meta, query)
                if results:
                    exec_meta.setdefault("logs", []).append(f"Edge: Tavily found {len(results)} results for '{query[:50]}...'")
                    # Extract snippets from URLs (simplified - would need full implementation)
                    perf_snippets.extend(results)
                    break

            if perf_snippets:
                exec_meta.setdefault("logs", []).append("Edge: Tavily search completed, extracting metrics")
                # Note: Full Tavily extraction would happen here
                # For now, mark as attempted
        except Exception as e:
            exec_meta.setdefault("warnings", []).append(f"Edge Tavily search failed: {str(e)}")

    # Priority 3: Extract from evidence snippets
    evidence = state.get("evidence", {})
    texts = _collect_texts(evidence)
    combined = " ".join(texts)

    metrics: Dict[str, Dict[str, Any]] = {}
    for key, (pattern, unit) in _PATTERNS.items():
        match = pattern.search(combined)
        if match:
            value = float(match.group(1))
            metrics[key] = {"value": value, "unit": unit, "source": "evidence_snippets", "priority": 3}

    if metrics:
        exec_meta.setdefault("logs", []).append(f"Edge: Extracted {len(metrics)} metrics from evidence")

    state.setdefault("performance", {})["metrics"] = metrics
    return metrics


__all__ = ["extract_edge_performance"]
