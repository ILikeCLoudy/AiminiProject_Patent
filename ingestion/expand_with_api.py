"""API expansion orchestrator implementing metric contract & placeholders."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from adapters.api_clients import (
    METRIC_KEYS,
    ApiBudgetExceeded,
    build_budget_placeholders,
    collect_api_metrics,
)


def _group_rows(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["metric_key"]].append(row)
    return grouped


def _extract_chosen_values(grouped: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    chosen: Dict[str, Dict[str, Any]] = {}
    for key, entries in grouped.items():
        selected = next((row for row in entries if row.get("chosen")), entries[0])
        chosen[key] = selected
    return chosen


def _score_from_api(chosen: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Derive scoring overrides from chosen API metrics."""
    scores: Dict[str, float] = {}

    family_size = chosen.get("FAMILY_SIZE", {}).get("value") or 0
    countries = chosen.get("COUNTRIES", {}).get("value") or []
    legal_status = (chosen.get("RENEWAL_STATUS") or {}).get("value") or ""
    sep_status = (chosen.get("SEP_INDICATION") or {}).get("value") or ""
    generality = chosen.get("GENERALITY", {}).get("value")
    originality = chosen.get("ORIGINALITY", {}).get("value")
    litigation_flag = (chosen.get("LITIGATION_FLAG") or {}).get("value")

    scores["family"] = min(95.0, 45.0 + (family_size or 0) * 7.5)
    scores["foreign"] = 80.0 if countries else 45.0
    scores["legal"] = 88.0 if isinstance(legal_status, str) and legal_status.lower() == "active" else 60.0
    scores["renewal"] = 55.0 if legal_status.lower() == "active" else 40.0
    scores["std"] = 78.0 if isinstance(sep_status, str) and "declared" in sep_status else 30.0
    scores["fto"] = -20.0 if litigation_flag else 0.0
    if generality is not None:
        scores["generality"] = float(generality)
    if originality is not None:
        scores["originality"] = float(originality)
    return scores


def _update_state(
    state: Dict[str, Any],
    rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> None:
    grouped = _group_rows(rows)
    chosen = _extract_chosen_values(grouped)

    api_state = state.setdefault("api", {})
    api_state["rows"] = rows
    api_state["summary"] = summary
    api_state["missing_keys"] = summary.get("missing_keys", [])

    state["api_meta"] = rows  # contract guarantee

    provenance = state.setdefault("provenance", {})
    provenance.setdefault("api_metrics", []).append(
        {
            "doc_id": summary.get("doc_id", "unknown"),
            "timestamp": summary.get("ts"),
            "collected_keys": summary.get("collected_keys", []),
            "missing_keys": summary.get("missing_keys", []),
        }
    )

    exec_meta = state.setdefault("exec_meta", {})
    badges = exec_meta.setdefault("source_badges", {})
    badges.update(
        {
            "family": "API meta",
            "foreign": "API meta",
            "legal": "API meta",
            "renewal": "API meta",
            "std": "API meta",
            "fto": "API meta",
            "generality": "API meta",
            "originality": "API meta",
        }
    )

    scores = state.setdefault("scores", {})
    overrides = _score_from_api(chosen)
    scores.update({key: value for key, value in overrides.items() if value is not None})

    routing = state.setdefault("routing", {})
    routing["priority"] = "claims" if (chosen.get("FAMILY_SIZE", {}).get("value") or 0) >= 3 else "trl"
    routing["has_sep"] = bool(chosen.get("SEP_INDICATION", {}).get("value"))

    state.setdefault("api_missing_flags", summary.get("missing_keys", []))


def _build_summary(exec_meta: Dict[str, Any], rows: List[Dict[str, Any]], *, doc_id: str) -> Dict[str, Any]:
    grouped = _group_rows(rows)
    collected_keys = sorted(grouped.keys())
    missing_keys = sorted(key for key in METRIC_KEYS if key not in grouped or all(row["value"] in (None, []) for row in grouped[key]))
    ok_count = sum(1 for key in grouped if any(row["status"] == "ok" for row in grouped[key]))

    api_meta = exec_meta.get("api", {})
    summary = {
        "doc_id": doc_id,
        "collected_keys": collected_keys,
        "missing_keys": missing_keys,
        "ok_count": ok_count,
        "total_metrics": len(METRIC_KEYS),
        "calls": api_meta.get("calls", 0),
        "cached": api_meta.get("cached", 0),
        "batches": api_meta.get("batches", 0),
        "ts": exec_meta.get("ts"),
        "cache_hits": api_meta.get("cached", 0),
        "budget_used_total": api_meta.get("calls", 0),
    }
    return summary


def expand_with_api(state: Dict[str, Any]) -> Dict[str, Any]:
    """Expand state with API-provided metrics according to contract."""
    config = state.get("config", {})
    api_cfg = config.get("api", {}) or {}
    exec_meta = state.setdefault("exec_meta", {})

    metas: List[Dict[str, Any]] = state.get("inputs", {}).get("metas", [])
    primary_meta = metas[0] if metas else {}
    doc_id = primary_meta.get("doc_id", "unknown")

    if not api_cfg.get("enabled", False):
        rows = build_budget_placeholders(doc_id, reason="api_disabled", exec_meta=exec_meta)
        summary = _build_summary(exec_meta, rows, doc_id=doc_id)
        summary["meta"] = {"enabled": False}
        _update_state(state, rows, summary)
        return {"ok": False, "summary": summary, "warnings": ["API disabled in configuration."]}

    ttl_days = int(api_cfg.get("cache_ttl_days", config.get("cache_ttl_days", 30)))
    cache_dir = Path(api_cfg.get("cache_dir", "cache/api_meta"))

    warnings: List[str] = []
    try:
        rows = collect_api_metrics(
            doc_id=doc_id,
            meta=primary_meta,
            api_config=api_cfg,
            exec_meta=exec_meta,
            cache_dir=cache_dir,
            ttl_days=ttl_days,
        )
    except ApiBudgetExceeded as exc:
        warnings.append(str(exc))
        rows = build_budget_placeholders(doc_id, reason="budget_exceeded", exec_meta=exec_meta)

    summary = _build_summary(exec_meta, rows, doc_id=doc_id)
    summary["meta"] = {"enabled": True}
    summary["warnings"] = warnings

    _update_state(state, rows, summary)
    return {"ok": not warnings, "summary": summary, "warnings": warnings}


__all__ = ["expand_with_api"]
