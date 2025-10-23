"""Structured output writers for downstream adapters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import csv

try:  # pragma: no cover - optional dependency
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pa = None  # type: ignore
    pq = None  # type: ignore


def _normalise_api_row(row: Dict[str, Any]) -> Dict[str, Any]:
    cache_info = row.get("cache_info") or {}
    value = row.get("value")
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return {
        "metric": row.get("metric_key"),
        "value": value,
        "unit": row.get("unit"),
        "year": row.get("year"),
        "source": row.get("source_name"),
        "source_id": row.get("source_id"),
        "url": row.get("source_url"),
        "status": row.get("status"),
        "chosen": bool(row.get("chosen")),
        "error": row.get("error"),
        "cache_hit": bool(cache_info.get("hit")),
        "cache_age_s": cache_info.get("age_s"),
        "budget_used": row.get("budget_used"),
        "retries": row.get("retries"),
    }


def write_structured_outputs(
    scores: Dict[str, Any],
    evidence: Dict[str, Any],
    *,
    api_rows: Iterable[Dict[str, Any]] | None = None,
    decision: Dict[str, Any] | None = None,
    summary_card: Dict[str, Any] | None = None,
) -> None:
    """Persist CSV and parquet artifacts that reflect score breakdowns & API contract.

    The CSV file provides a lightweight summary for spreadsheet consumers, while
    the parquet tables capture structured metrics for adapters that expect typed
    columns (e.g., downstream dashboards or QA automation).
    """
    reports_dir = Path("reports")
    outputs_dir = Path("outputs")
    reports_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)

    api_rows = list(api_rows or [])
    api_csv_path = reports_dir / "api_metrics.csv"
    with api_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "metric",
                "value",
                "unit",
                "year",
                "source",
                "source_id",
                "url",
                "status",
                "chosen",
                "error",
                "cache_hit",
                "cache_age_s",
                "budget_used",
                "retries",
            ]
        )
        for row in api_rows:
            normalised = _normalise_api_row(row)
            writer.writerow(
                [
                    normalised["metric"],
                    normalised["value"],
                    normalised["unit"],
                    normalised["year"],
                    normalised["source"],
                    normalised["source_id"],
                    normalised["url"],
                    normalised["status"],
                    normalised["chosen"],
                    normalised["error"],
                    normalised["cache_hit"],
                    normalised["cache_age_s"],
                    normalised["budget_used"],
                    normalised["retries"],
                ]
            )

    scores_csv_path = reports_dir / "scores.csv"
    with scores_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for metric, value in scores.items():
            if isinstance(value, (int, float)):
                writer.writerow([metric, f"{float(value):.2f}"])
            else:
                writer.writerow([metric, ""])

    if summary_card:
        summary_path = reports_dir / "summary_card.csv"
        with summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["field", "value"])
            writer.writerow(["conclusion", summary_card.get("conclusion")])
            writer.writerow(["reasons", " | ".join(summary_card.get("reasons", []))])
            purpose_scope = summary_card.get("purpose_scope", {})
            writer.writerow(["purpose", purpose_scope.get("purpose")])
            scope = purpose_scope.get("scope", {})
            writer.writerow(["scope_keywords", scope.get("keywords")])
            writer.writerow(["scope_cpc", scope.get("cpc")])
            writer.writerow(["scope_period", scope.get("period")])
            writer.writerow(["scope_target_market", scope.get("target_market")])
            top_line = summary_card.get("top_line", {})
            writer.writerow(["documents", top_line.get("documents")])
            writer.writerow(["family_size", top_line.get("family_size")])
            writer.writerow(["country_count", top_line.get("country_count")])
            writer.writerow(["label", top_line.get("label")])

    score_meta = (decision or {}).get("weights_meta", {})
    weights_csv_path = reports_dir / "weight_contributions.csv"
    with weights_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "weight_share"])
        for metric, share in score_meta.get("contributions", {}).items():
            writer.writerow([metric, f"{share:.4f}"])

    if pa is None or pq is None:  # pragma: no cover - fallback when pyarrow missing
        return

    api_table = pa.Table.from_pylist(
        [_normalise_api_row(row) for row in api_rows],
        schema=pa.schema(
            [
                ("metric", pa.string()),
                ("value", pa.string()),
                ("unit", pa.string()),
                ("year", pa.int32()),
                ("source", pa.string()),
                ("source_id", pa.string()),
                ("url", pa.string()),
                ("status", pa.string()),
                ("chosen", pa.bool_()),
                ("error", pa.string()),
                ("cache_hit", pa.bool_()),
                ("cache_age_s", pa.float64()),
                ("budget_used", pa.int64()),
                ("retries", pa.int64()),
            ]
        ),
    )
    pq.write_table(api_table, outputs_dir / "api_metrics.parquet")

    core_rows: List[Dict[str, Any]] = []
    for metric, value in scores.items():
        coerced = float(value) if isinstance(value, (int, float)) else None
        core_rows.append({"metric": metric, "value": coerced})
    core_table = pa.Table.from_pylist(
        core_rows,
        schema=pa.schema([("metric", pa.string()), ("value", pa.float64())]),
    )
    pq.write_table(core_table, outputs_dir / "core_scores.parquet")

    evidence_rows: List[Dict[str, Any]] = []
    for metric, payload in evidence.items():
        snippets = payload.get("snippets", [])
        for snippet in snippets:
            evidence_rows.append(
                {
                    "metric": metric,
                    "badge": snippet.get("badge"),
                    "source": snippet.get("source"),
                    "source_type": snippet.get("source_type"),
                    "doc_ref": snippet.get("doc_ref"),
                    "status": snippet.get("status", "ok"),
                    "error": snippet.get("error"),
                }
            )
    adapter_table = pa.Table.from_pylist(
        evidence_rows,
        schema=pa.schema(
            [
                ("metric", pa.string()),
                ("badge", pa.string()),
                ("source", pa.string()),
                ("source_type", pa.string()),
                ("doc_ref", pa.string()),
                ("status", pa.string()),
                ("error", pa.string()),
            ]
        ),
    )
    pq.write_table(adapter_table, outputs_dir / "adapter_scores.parquet")


__all__ = ["write_structured_outputs"]
