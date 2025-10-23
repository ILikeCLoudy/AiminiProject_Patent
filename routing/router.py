"""Routing module to select patent candidates based on natural language queries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_catalog(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog_cfg = config.get("catalog", {}) or {}
    path = catalog_cfg.get("path")
    if not path:
        return []
    catalog_path = Path(path)
    if not catalog_path.exists():
        return []
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        data = json.loads(catalog_path.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def _score_candidate(query: str, candidate: Dict[str, Any]) -> float:
    query_lower = query.lower()
    keywords = candidate.get("keywords", []) or []
    score = 0.0
    for keyword in keywords:
        if keyword.lower() in query_lower:
            score += 1.0
    title = candidate.get("title")
    if isinstance(title, str) and title.lower() in query_lower:
        score += 0.5
    cpc = candidate.get("cpc", []) or []
    for code in cpc:
        if code.lower() in query_lower:
            score += 0.3
    return score


def select_candidates(query: str, config: Dict[str, Any], top_k: int | None = None) -> List[Dict[str, Any]]:
    catalog = _load_catalog(config)
    if not catalog:
        return []
    scored: List[Dict[str, Any]] = []
    for entry in catalog:
        score = _score_candidate(query, entry)
        enriched = dict(entry)
        enriched["score"] = score
        scored.append(enriched)
    scored.sort(key=lambda item: item["score"], reverse=True)
    limit = top_k or config.get("catalog", {}).get("top_k", 5)
    if limit:
        scored = scored[:limit]
    return scored


__all__ = ["select_candidates"]
