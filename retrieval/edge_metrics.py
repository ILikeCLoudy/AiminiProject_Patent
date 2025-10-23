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
    """Extract latency/power/memory/accuracy deltas from evidence texts."""
    evidence = state.get("evidence", {})
    texts = _collect_texts(evidence)
    combined = " ".join(texts)

    metrics: Dict[str, Dict[str, Any]] = {}
    for key, (pattern, unit) in _PATTERNS.items():
        match = pattern.search(combined)
        if match:
            value = float(match.group(1))
            metrics[key] = {"value": value, "unit": unit, "source": "evidence_snippets"}

    state.setdefault("performance", {})["metrics"] = metrics
    return metrics


__all__ = ["extract_edge_performance"]
