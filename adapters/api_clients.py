"""Mockable API client utilities with caching and budget enforcement."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


class ApiBudgetExceeded(RuntimeError):
    """Raised when API call budget is exhausted."""


DEFAULT_METRICS: Tuple[str, ...] = (
    "family_size",
    "forward_citations_5y",
    "countries",
    "legal_status",
    "renewal_years",
    "foreign_oriented",
    "sep_declared",
    "std_participation",
    "hhi",
    "generality",
    "originality",
)


@dataclass
class ApiCacheEntry:
    metrics: Dict[str, Any]
    timestamp: str

    @classmethod
    def load(cls, path: Path) -> "ApiCacheEntry | None":
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        metrics = payload.get("metrics")
        timestamp = payload.get("timestamp")
        if not isinstance(metrics, dict) or not isinstance(timestamp, str):
            return None
        return cls(metrics=metrics, timestamp=timestamp)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"metrics": self.metrics, "timestamp": self.timestamp}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_path(cache_dir: Path, doc_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in doc_id)
    return cache_dir / f"{safe_id}.json"


def _compute_metrics(meta: Dict[str, Any]) -> Dict[str, Any]:
    family_size = int(meta.get("family_size") or 0)
    forward_citations = int(meta.get("forward_citations_5y") or 0)
    countries = list(meta.get("countries", []))
    legal_status = meta.get("legal_status") or "unknown"
    renewal_years = int(meta.get("renewal_years") or 0)
    foreign_oriented = bool(meta.get("foreign_oriented"))
    sep_declared = bool(meta.get("sep_declared"))
    std_participation = bool(meta.get("std_participation"))
    unique_countries = {code.upper() for code in countries if isinstance(code, str)}

    market_span = max(len(unique_countries), 1)
    hhi = round(100.0 / market_span, 4)
    generality = max(0.0, 100.0 - hhi)
    originality = min(100.0, 40.0 + family_size * 8.0 + forward_citations * 2.0)

    return {
        "family_size": family_size,
        "forward_citations_5y": forward_citations,
        "countries": sorted(unique_countries),
        "legal_status": legal_status,
        "renewal_years": renewal_years,
        "foreign_oriented": foreign_oriented,
        "sep_declared": sep_declared,
        "std_participation": std_participation,
        "hhi": hhi,
        "generality": generality,
        "originality": originality,
    }


def _validate_domains(domains: Iterable[str], whitelist: Iterable[str]) -> None:
    allowed = {domain.lower() for domain in whitelist}
    disallowed = [domain for domain in domains if domain.lower() not in allowed]
    if disallowed:
        raise ValueError(f"Domains not permitted by whitelist: {', '.join(disallowed)}")


def fetch_metrics(
    *,
    doc_id: str,
    meta: Dict[str, Any],
    api_config: Dict[str, Any],
    exec_meta: Dict[str, Any],
    cache_dir: Path,
    ttl_days: int,
) -> Dict[str, Any]:
    """Fetch patent metrics with cache + budget enforcement."""
    if not doc_id:
        raise ValueError("doc_id is required for API expansion.")

    api_meta = exec_meta.setdefault("api", {})
    max_calls = int(api_config.get("max_calls_per_run", 200))
    batch_size = max(1, int(api_config.get("batch_size", 20)))
    whitelist = api_config.get("whitelist_domains") or []
    domains = meta.get("api_domains") or []
    if whitelist:
        _validate_domains(domains or whitelist, whitelist)

    used_calls = int(api_meta.get("calls", 0))
    if used_calls >= max_calls:
        raise ApiBudgetExceeded(f"API call budget exhausted: limit={max_calls}")

    cache_file = _cache_path(cache_dir, doc_id)
    cache_entry = ApiCacheEntry.load(cache_file)
    if cache_entry:
        from datetime import datetime, timedelta

        try:
            cached_at = datetime.fromisoformat(cache_entry.timestamp)
        except ValueError:
            cached_at = None
        if cached_at and datetime.now() - cached_at < timedelta(days=max(ttl_days, 1)):
            api_meta["cached"] = api_meta.get("cached", 0) + 1
            api_meta.setdefault("batches", 0)
            return cache_entry.metrics

    metrics = _compute_metrics(meta)

    batches = math.ceil(len(DEFAULT_METRICS) / batch_size)
    api_meta["calls"] = used_calls + 1
    api_meta["batches"] = api_meta.get("batches", 0) + batches
    api_meta.setdefault("cached", 0)

    from datetime import datetime

    ApiCacheEntry(metrics=metrics, timestamp=datetime.now().isoformat()).save(cache_file)
    return metrics


__all__ = ["fetch_metrics", "ApiBudgetExceeded", "DEFAULT_METRICS"]
