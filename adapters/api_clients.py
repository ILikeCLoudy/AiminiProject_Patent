"""Deterministic API adapter utilities implementing the 10-metric contract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


class ApiBudgetExceeded(RuntimeError):
    """Raised when API call budget is exhausted."""


# Canonical metric keys (upper-case as required by contract)
METRIC_KEYS: Tuple[str, ...] = (
    "CITATIONS_TOTAL",
    "FAMILY_SIZE",
    "COUNTRIES",
    "LITIGATION_FLAG",
    "RENEWAL_STATUS",
    "SEP_INDICATION",
    "HHI",
    "GENERALITY",
    "ORIGINALITY",
    "AGE_YEARS",
)


# Canonical source definitions per metric (recency -> officialness -> quality selection)
SOURCE_DEFS: Dict[str, List[Dict[str, Any]]] = {
    "CITATIONS_TOTAL": [
        {
            "source_name": "NBER Working Paper 7741",
            "source_id": "NBER-W7741",
            "url": "https://www.nber.org/papers/w7741",
            "domain": "nber.org",
            "year": 2000,
            "unit": "count",
            "officialness": 2,
            "quality": 3,
        },
        {
            "source_name": "Google Patents",
            "source_id": "GOOGLE-PATENTS",
            "url": "https://patents.google.com/patent/{doc_id}",
            "domain": "patents.google.com",
            "year": datetime.now().year,
            "unit": "count",
            "officialness": 1,
            "quality": 2,
        },
    ],
    "FAMILY_SIZE": [
        {
            "source_name": "WIPO IP Indicators",
            "source_id": "WIPO-2024",
            "url": "https://www.wipo.int/web-publications/world-intellectual-property-indicators-2024-highlights/en/patents-highlights.html",
            "domain": "wipo.int",
            "year": 2024,
            "unit": "count",
            "officialness": 3,
            "quality": 3,
        }
    ],
    "COUNTRIES": [
        {
            "source_name": "WIPO IP Indicators",
            "source_id": "WIPO-2024",
            "url": "https://www.wipo.int/web-publications/world-intellectual-property-indicators-2024-highlights/en/patents-highlights.html",
            "domain": "wipo.int",
            "year": 2024,
            "unit": "countries",
            "officialness": 3,
            "quality": 2,
        }
    ],
    "LITIGATION_FLAG": [
        {
            "source_name": "USPTO Official Gazette",
            "source_id": "USPTO-OG-2012-52",
            "url": "https://www.uspto.gov/web/offices/com/sol/og/2012/week52/TOCCN/item-80.htm",
            "domain": "uspto.gov",
            "year": 2012,
            "unit": "boolean",
            "officialness": 3,
            "quality": 1,
        },
        {
            "source_name": "WIPO Magazine - Freedom to Operate",
            "source_id": "WIPO-FTO-ARTICLE",
            "url": "https://www.wipo.int/en/web/wipo-magazine/articles/ip-and-business-launching-a-new-product-freedom-to-operate-34956",
            "domain": "wipo.int",
            "year": 2005,
            "unit": "boolean",
            "officialness": 2,
            "quality": 2,
        },
    ],
    "RENEWAL_STATUS": [
        {
            "source_name": "USPTO Maintenance Fee",
            "source_id": "USPTO-FEE",
            "url": "https://www.uspto.gov/web/offices/com/sol/og/2012/week52/TOCCN/item-80.htm",
            "domain": "uspto.gov",
            "year": 2012,
            "unit": "status",
            "officialness": 3,
            "quality": 2,
        }
    ],
    "SEP_INDICATION": [
        {
            "source_name": "ETSI SEP List",
            "source_id": "ETSI-SR-000-314",
            "url": "https://www.etsi.org/deliver/etsi_sr/000300_000399/000314/02.32.01_60/sr_000314v023201p.pdf",
            "domain": "etsi.org",
            "year": 2022,
            "unit": "boolean",
            "officialness": 3,
            "quality": 3,
        }
    ],
    "HHI": [
        {
            "source_name": "DOJ / FTC Guidelines",
            "source_id": "DOJ-HHI",
            "url": "https://www.justice.gov/atr/herfindahl-hirschman-index",
            "domain": "justice.gov",
            "year": 2024,
            "unit": "index",
            "officialness": 3,
            "quality": 2,
        }
    ],
    "GENERALITY": [
        {
            "source_name": "NBER Working Paper 8498",
            "source_id": "NBER-W8498",
            "url": "https://www.nber.org/papers/w8498",
            "domain": "nber.org",
            "year": 2001,
            "unit": "index",
            "officialness": 2,
            "quality": 3,
        }
    ],
    "ORIGINALITY": [
        {
            "source_name": "NBER Working Paper 7741",
            "source_id": "NBER-W7741",
            "url": "https://www.nber.org/papers/w7741",
            "domain": "nber.org",
            "year": 2000,
            "unit": "index",
            "officialness": 2,
            "quality": 3,
        }
    ],
    "AGE_YEARS": [
        {
            "source_name": "Google Patents",
            "source_id": "GOOGLE-PATENTS",
            "url": "https://patents.google.com/patent/{doc_id}",
            "domain": "patents.google.com",
            "year": datetime.now().year,
            "unit": "years",
            "officialness": 1,
            "quality": 2,
        }
    ],
}


@dataclass
class ApiCacheEntry:
    """Persisted cache entry for deterministic API responses."""

    timestamp: str
    records: List[Dict[str, Any]]

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
        ts = payload.get("timestamp")
        records = payload.get("records")
        if not isinstance(ts, str) or not isinstance(records, list):
            return None
        return cls(timestamp=ts, records=records)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": self.timestamp, "records": self.records}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_path(cache_dir: Path, doc_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in doc_id)
    return cache_dir / f"{safe_id}.json"


def _normalize_whitelist(whitelist: Iterable[str]) -> set[str]:
    return {domain.lower() for domain in whitelist or []}


def _domain_allowed(domain: str, whitelist: set[str]) -> bool:
    if not whitelist:
        return True
    return domain.lower() in whitelist


def _compute_base_metrics(meta: Dict[str, Any], exec_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Derive deterministic metric values from provided metadata."""
    publication_date = meta.get("publication_date")
    age_years: float | None = None
    if publication_date:
        try:
            pub_dt = datetime.fromisoformat(publication_date)
        except ValueError:
            try:
                pub_dt = datetime.strptime(publication_date, "%Y-%m-%d")
            except ValueError:
                pub_dt = None
        if pub_dt:
            ts_value = exec_meta.get("ts")
            now = datetime.fromisoformat(ts_value) if isinstance(ts_value, str) else datetime.now()
            age_years = max((now - pub_dt).days / 365.25, 0.0)

    family_size = int(meta.get("family_size") or 0)
    citations = int(meta.get("forward_citations_5y") or meta.get("citations_total") or 0)
    countries_raw = meta.get("countries") or []
    countries = sorted({code.upper() for code in countries_raw if isinstance(code, str)})
    renewal_years = int(meta.get("renewal_years") or 0)
    sep = bool(meta.get("sep_declared"))
    litigation = bool(meta.get("litigation_flag")) if meta.get("litigation_flag") is not None else None
    foreign_oriented = bool(meta.get("foreign_oriented"))
    legal_status = meta.get("legal_status") or "unknown"

    market_span = max(len(countries), 1)
    hhi = round(100.0 / market_span, 4)
    generality = round(max(0.0, 100.0 - hhi), 4)
    originality = round(
        min(100.0, 45.0 + family_size * 6.0 + citations * 1.5),
        4,
    )

    renewal_status = "active" if renewal_years > 0 else "unknown"
    sep_status = "declared" if sep else "not_declared"

    return {
        "CITATIONS_TOTAL": citations,
        "FAMILY_SIZE": family_size,
        "COUNTRIES": countries,
        "LITIGATION_FLAG": litigation,
        "RENEWAL_STATUS": renewal_status,
        "SEP_INDICATION": sep_status if sep or renewal_status != "unknown" else None,
        "HHI": hhi,
        "GENERALITY": generality,
        "ORIGINALITY": originality,
        "AGE_YEARS": round(age_years, 2) if age_years is not None else None,
    }


def _build_record(
    *,
    metric_key: str,
    value: Any,
    source: Dict[str, Any],
    doc_id: str,
    fetch_ts: str,
    status: str,
    error: str | None,
    cache_hit: bool,
    cache_age_s: float | None,
    budget_used: int,
    retries: int,
) -> Dict[str, Any]:
    url = source["url"].format(doc_id=doc_id)
    cache_info = {"hit": cache_hit}
    if cache_age_s is not None:
        cache_info["age_s"] = cache_age_s
    record = {
        "metric_key": metric_key,
        "value": value,
        "unit": source.get("unit"),
        "year": source.get("year"),
        "source_name": source["source_name"],
        "source_type": "API",
        "source_id": source["source_id"],
        "source_url": url,
        "fetch_ts": fetch_ts,
        "cache_info": cache_info,
        "budget_used": budget_used,
        "retries": retries,
        "status": status,
        "error": error,
        "chosen": False,
    }
    return record


def _select_chosen(records: List[Dict[str, Any]]) -> None:
    """Mark chosen=True according to recency > officialness > quality."""
    if not records:
        return
    best = max(
        records,
        key=lambda row: (
            1 if row["status"] == "ok" and row.get("value") is not None else 0,
            row.get("year") or 0,
            next(
                (
                    src.get("officialness", 0)
                    for src in SOURCE_DEFS.get(row["metric_key"], [])
                    if src["source_id"] == row["source_id"]
                ),
                0,
            ),
            next(
                (
                    src.get("quality", 0)
                    for src in SOURCE_DEFS.get(row["metric_key"], [])
                    if src["source_id"] == row["source_id"]
                ),
                0,
            ),
        ),
    )
    best["chosen"] = True


def collect_api_metrics(
    *,
    doc_id: str,
    meta: Dict[str, Any],
    api_config: Dict[str, Any],
    exec_meta: Dict[str, Any],
    cache_dir: Path,
    ttl_days: int,
) -> List[Dict[str, Any]]:
    """Return adapter rows for the 10 deterministic metrics."""
    if not doc_id:
        raise ValueError("doc_id is required for API expansion.")

    api_meta = exec_meta.setdefault("api", {})
    max_calls = int(api_config.get("max_calls_per_run", 200))
    used_calls = int(api_meta.get("calls", 0))
    whitelist = _normalize_whitelist(api_config.get("whitelist_domains") or [])

    if api_config.get("use_fixed_values"):
        fixed = api_config.get("fixed_metrics") or {}
        now = datetime.now(timezone.utc).isoformat()
        records: List[Dict[str, Any]] = []
        ok_count = 0
        missing_keys: List[str] = []
        for metric_key in METRIC_KEYS:
            entry = fixed.get(metric_key, {})
            sources = SOURCE_DEFS.get(metric_key, [])
            source = sources[0] if sources else {
                "source_name": "Fixed Metric",
                "source_id": "FIXED",
                "url": "",
                "domain": "",
                "year": datetime.now().year,
                "unit": entry.get("unit"),
                "officialness": 0,
                "quality": 0,
            }
            value = entry.get("value")
            unit = entry.get("unit", source.get("unit"))
            year = entry.get("year", source.get("year"))
            status = "ok" if value is not None else "missing"
            if status == "ok":
                ok_count += 1
            else:
                missing_keys.append(metric_key)
            record = _build_record(
                metric_key=metric_key,
                value=value,
                source=source,
                doc_id=doc_id,
                fetch_ts=now,
                status=status,
                error=None if status == "ok" else "fixed_value_missing",
                cache_hit=True,
                cache_age_s=0.0,
                budget_used=0,
                retries=0,
            )
            record["unit"] = unit or source.get("unit")
            record["year"] = year or source.get("year")
            record["chosen"] = True
            records.append(record)
        api_meta["calls"] = used_calls
        api_meta["cached"] = api_meta.get("cached", 0) + 1
        api_meta["batches"] = api_meta.get("batches", 0)
        api_meta["fixed"] = True
        api_meta["missing_keys"] = missing_keys
        api_meta["ok_count"] = ok_count
        api_meta["collected_keys"] = list(METRIC_KEYS)
        api_meta["last_fetch_ts"] = now
        return records

    cache_file = _cache_path(cache_dir, doc_id)
    cache_entry = ApiCacheEntry.load(cache_file)
    now = datetime.now(timezone.utc)
    cache_hit = False
    cache_age_s: float | None = None

    if cache_entry:
        try:
            cached_at = datetime.fromisoformat(cache_entry.timestamp)
        except ValueError:
            cached_at = None
        if cached_at and now - cached_at < timedelta(days=max(ttl_days, 1)):
            cache_hit = True
            cache_age_s = (now - cached_at).total_seconds()
            api_meta["cached"] = api_meta.get("cached", 0) + 1
            api_meta.setdefault("calls", used_calls)
            api_meta.setdefault("batches", 0)
            records = cache_entry.records
            for record in records:
                record["cache_info"] = {"hit": True, "age_s": cache_age_s}
            return records

    if used_calls >= max_calls:
        raise ApiBudgetExceeded(f"API call budget exhausted: limit={max_calls}")

    base_metrics = _compute_base_metrics(meta, exec_meta)
    fetch_ts = now.isoformat()
    records: List[Dict[str, Any]] = []
    missing_metrics: List[str] = []

    for metric_key in METRIC_KEYS:
        metric_sources = SOURCE_DEFS.get(metric_key, [])
        metric_value = base_metrics.get(metric_key)
        metric_status = "ok" if metric_value not in (None, []) else "missing"
        error = None if metric_status == "ok" else "no_adapter_result"

        metric_rows: List[Dict[str, Any]] = []
        for source in metric_sources:
            domain = source["domain"]
            allowed = _domain_allowed(domain, whitelist)
            status = metric_status if allowed else "blocked_domain"
            row_error = error if allowed else "domain_not_whitelisted"
            value = metric_value if allowed else None
            row = _build_record(
                metric_key=metric_key,
                value=value,
                source=source,
                doc_id=doc_id,
                fetch_ts=fetch_ts,
                status=status,
                error=row_error,
                cache_hit=cache_hit,
                cache_age_s=cache_age_s,
                budget_used=1,
                retries=1,
            )
            metric_rows.append(row)

        if not metric_rows:
            # No adapter registered; produce placeholder shell.
            placeholder = _build_record(
                metric_key=metric_key,
                value=None,
                source={
                    "source_name": "Adapter Missing",
                    "source_id": "ADAPTER-MISSING",
                    "url": "https://example.com/",
                    "domain": "example.com",
                    "year": now.year,
                    "unit": None,
                    "officialness": 0,
                    "quality": 0,
                },
                doc_id=doc_id,
                fetch_ts=fetch_ts,
                status="missing",
                error="no_adapter_result",
                cache_hit=cache_hit,
                cache_age_s=cache_age_s,
                budget_used=1,
                retries=0,
            )
            metric_rows.append(placeholder)

        if all(row["status"] != "ok" for row in metric_rows):
            missing_metrics.append(metric_key)

        _select_chosen(metric_rows)
        records.extend(metric_rows)

    batches = int(api_config.get("batch_size", 10))
    api_meta["calls"] = used_calls + 1
    api_meta["batches"] = api_meta.get("batches", 0) + max(1, len(METRIC_KEYS) // max(batches, 1))
    api_meta["last_fetch_ts"] = fetch_ts
    api_meta["missing_keys"] = missing_metrics
    api_meta.setdefault("cached", 0)
    ApiCacheEntry(timestamp=fetch_ts, records=records).save(cache_file)
    return records


def build_budget_placeholders(doc_id: str, *, reason: str, exec_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return placeholder rows for all metrics when budget is exhausted."""
    now = datetime.now(timezone.utc).isoformat()
    rows: List[Dict[str, Any]] = []
    for metric_key in METRIC_KEYS:
        primary_source = SOURCE_DEFS.get(metric_key, [{}])[0] if SOURCE_DEFS.get(metric_key) else {
            "source_name": "Adapter Missing",
            "source_id": "ADAPTER-MISSING",
            "url": "https://example.com/",
            "domain": "example.com",
            "year": datetime.now().year,
            "unit": None,
            "officialness": 0,
            "quality": 0,
        }
        row = _build_record(
            metric_key=metric_key,
            value=None,
            source=primary_source,
            doc_id=doc_id or "unknown",
            fetch_ts=now,
            status="budget_exceeded",
            error=reason,
            cache_hit=False,
            cache_age_s=None,
            budget_used=0,
            retries=0,
        )
        row["chosen"] = True
        rows.append(row)
    api_meta = exec_meta.setdefault("api", {})
    api_meta.setdefault("missing_keys", list(METRIC_KEYS))
    return rows


__all__ = ["collect_api_metrics", "build_budget_placeholders", "ApiBudgetExceeded", "METRIC_KEYS"]
