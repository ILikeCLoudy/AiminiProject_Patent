"""Edge performance metric extraction from evidence snippets."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse


_PATTERNS: Dict[str, Tuple[re.Pattern[str], str]] = {
    "latency_ms": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:ms|millisecond)", re.IGNORECASE), "ms"),
    "power_mw": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:mw|milliwatt)", re.IGNORECASE), "mW"),
    "memory_mb": (re.compile(r"(\d+(?:\.\d+)?)\s*(?:mb|megabyte)", re.IGNORECASE), "MB"),
    "accuracy_delta": (re.compile(r"accuracy\s+delta\s+(?:of\s+)?(?:-)?(\d+(?:\.\d+)?)\s*%|(?:-)?(\d+(?:\.\d+)?)\s*%\s+.{0,30}accuracy", re.IGNORECASE), "%"),
}


def _domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc.lower()


def _extract_from_text(text: str, source_url: str) -> Dict[str, Dict[str, Any]]:
    """Extract performance metrics from text using regex patterns."""
    metrics: Dict[str, Dict[str, Any]] = {}
    source_domain = _domain(source_url)

    for key, (pattern, unit) in _PATTERNS.items():
        match = pattern.search(text)
        if match:
            # Handle multiple capture groups (e.g., accuracy_delta pattern)
            value = None
            for group in match.groups():
                if group is not None:
                    value = float(group)
                    break

            if value is not None:
                metrics[key] = {
                    "value": value,
                    "unit": unit,
                    "source": f"tavily:{source_domain}",
                    "source_url": source_url,
                    "priority": 2
                }

    return metrics


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

            tavily_metrics: Dict[str, Dict[str, Any]] = {}
            for query in queries[:2]:  # Limit to 2 queries to reduce API costs
                results = search_official_links(config, exec_meta, query)
                if not results:
                    continue

                exec_meta.setdefault("logs", []).append(f"Edge: Tavily found {len(results)} results for '{query[:50]}...'")

                # Download and extract text from whitelisted URLs
                for result in results[:3]:  # Process up to 3 URLs per query
                    url = result.get("url")
                    if not url:
                        continue

                    try:
                        snapshot_meta = snapshot_and_extract(config, exec_meta, url)
                        txt_path = snapshot_meta.get("txt_path")

                        if txt_path and os.path.exists(txt_path):
                            with open(txt_path, "r", encoding="utf-8") as f:
                                text = f.read()

                            # Extract metrics from downloaded content
                            extracted = _extract_from_text(text, url)
                            if extracted:
                                tavily_metrics.update(extracted)
                                exec_meta.setdefault("logs", []).append(
                                    f"Edge: Extracted {len(extracted)} metrics from {_domain(url)}"
                                )
                    except Exception as e:
                        exec_meta.setdefault("warnings", []).append(f"Edge: Failed to snapshot {url}: {str(e)}")
                        continue

                # If we found metrics, no need to try more queries
                if tavily_metrics:
                    break

            if tavily_metrics:
                state.setdefault("performance", {})["metrics"] = tavily_metrics
                exec_meta.setdefault("logs", []).append(
                    f"Edge: Tavily extraction completed with {len(tavily_metrics)} metrics"
                )
                return tavily_metrics
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
            # Handle multiple capture groups (e.g., accuracy_delta pattern)
            value = None
            for group in match.groups():
                if group is not None:
                    value = float(group)
                    break

            if value is not None:
                metrics[key] = {"value": value, "unit": unit, "source": "evidence_snippets", "priority": 3}

    if metrics:
        exec_meta.setdefault("logs", []).append(f"Edge: Extracted {len(metrics)} metrics from evidence")

    state.setdefault("performance", {})["metrics"] = metrics
    return metrics


__all__ = ["extract_edge_performance"]
