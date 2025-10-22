"""API expansion and metadata enrichment utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from adapters.api_clients import ApiBudgetExceeded, fetch_metrics


def _score_from_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    scores["family"] = min(95.0, 45.0 + metrics.get("family_size", 0) * 8.0)
    scores["foreign"] = 80.0 if metrics.get("foreign_oriented") else 45.0
    scores["legal"] = 88.0 if metrics.get("legal_status", "").lower() in {"granted", "active"} else 60.0
    scores["renewal"] = min(90.0, 45.0 + metrics.get("renewal_years", 0) * 6.0)
    scores["std"] = 78.0 if metrics.get("std_participation") else 30.0
    scores["fto"] = -20.0 if metrics.get("sep_declared") else 0.0
    scores["generality"] = float(metrics.get("generality", 0.0))
    scores["originality"] = float(metrics.get("originality", 0.0))
    return scores


def _update_state(state: Dict[str, Any], metrics: Dict[str, Any], summary: Dict[str, Any]) -> None:
    api_state = state.setdefault("api", {})
    api_state["metrics"] = metrics
    api_state["summary"] = summary

    provenance = state.setdefault("provenance", {})
    provenance.setdefault("api_metrics", []).append(
        {
            "doc_id": state.get("inputs", {}).get("metas", [{}])[0].get("doc_id", "unknown"),
            "metrics": list(metrics.keys()),
            "timestamp": summary.get("ts"),
        }
    )

    exec_meta = state.setdefault("exec_meta", {})
    exec_meta.setdefault("source_badges", {}).update(
        {
            "family": "API",
            "foreign": "API",
            "legal": "API",
            "renewal": "API",
            "std": "API",
            "fto": "API",
        }
    )

    scores = state.setdefault("scores", {})
    overrides = _score_from_metrics(metrics)
    scores.update({key: value for key, value in overrides.items() if value is not None})

    routing = state.setdefault("routing", {})
    routing["priority"] = "claims" if metrics.get("family_size", 0) >= 3 else "trl"
    routing["has_sep"] = bool(metrics.get("sep_declared"))


def expand_with_api(state: Dict[str, Any]) -> Dict[str, Any]:
    """Expand state with API-provided metrics (mocked via metadata fallback)."""
    config = state.get("config", {})
    api_cfg = config.get("api", {}) or {}
    exec_meta = state.setdefault("exec_meta", {})

    if not api_cfg.get("enabled", False):
        summary = {"calls": 0, "cached": 0, "meta": {"enabled": False}, "ts": exec_meta.get("ts")}
        _update_state(state, state.get("api", {}).get("metrics", {}), summary)
        return {"ok": False, "summary": summary, "warnings": []}

    metas: List[Dict[str, Any]] = state.get("inputs", {}).get("metas", [])
    primary_meta = metas[0] if metas else {}
    doc_id = primary_meta.get("doc_id", "unknown")
    ttl_days = int(api_cfg.get("cache_ttl_days", config.get("cache_ttl_days", 30)))
    cache_dir = Path(api_cfg.get("cache_dir", "cache/api_meta"))

    try:
        metrics = fetch_metrics(
            doc_id=doc_id,
            meta=primary_meta,
            api_config=api_cfg,
            exec_meta=exec_meta,
            cache_dir=cache_dir,
            ttl_days=ttl_days,
        )
    except ApiBudgetExceeded as exc:
        warning = str(exc)
        summary = {"calls": exec_meta.get("api", {}).get("calls", 0), "cached": exec_meta.get("api", {}).get("cached", 0), "meta": {"enabled": True}, "ts": exec_meta.get("ts")}
        return {"ok": False, "summary": summary, "warnings": [warning]}

    summary = {
        "calls": exec_meta.get("api", {}).get("calls", 0),
        "cached": exec_meta.get("api", {}).get("cached", 0),
        "batches": exec_meta.get("api", {}).get("batches", 0),
        "meta": {"enabled": True},
        "ts": exec_meta.get("ts"),
    }
    _update_state(state, metrics, summary)
    return {"ok": True, "summary": summary}


__all__ = ["expand_with_api"]
