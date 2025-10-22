"""Structured output writers for downstream adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import csv

try:  # pragma: no cover - optional dependency
    import pyarrow as pa  # type: ignore
    import pyarrow.parquet as pq  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pa = None  # type: ignore
    pq = None  # type: ignore


def write_structured_outputs(scores: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    """Persist CSV and parquet artifacts that reflect score breakdowns.

    The CSV file provides a lightweight summary for spreadsheet consumers, while
    the parquet tables capture structured metrics for adapters that expect typed
    columns (e.g., downstream dashboards or QA automation).
    """
    reports_dir = Path("reports")
    outputs_dir = Path("outputs")
    reports_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)

    topk_path = reports_dir / "topk.csv"
    with topk_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for metric, value in scores.items():
            if metric == "fto":
                continue
            if isinstance(value, (int, float)):
                writer.writerow([metric, f"{float(value):.2f}"])
            else:
                writer.writerow([metric, ""])

    if pa is None or pq is None:  # pragma: no cover - fallback when pyarrow missing
        return

    core_rows = []
    for metric, value in scores.items():
        coerced = float(value) if isinstance(value, (int, float)) else None
        core_rows.append({"metric": metric, "value": coerced})
    core_table = pa.Table.from_pylist(
        core_rows,
        schema=pa.schema([("metric", pa.string()), ("value", pa.float64())]),
    )
    pq.write_table(core_table, outputs_dir / "core_scores.parquet")

    evidence_counts = [
        {"metric": key, "snippets": len(payload.get("snippets", []))}
        for key, payload in evidence.items()
    ]
    adapter_table = pa.Table.from_pylist(
        evidence_counts,
        schema=pa.schema([("metric", pa.string()), ("snippets", pa.int64())]),
    )
    pq.write_table(adapter_table, outputs_dir / "adapter_scores.parquet")


__all__ = ["write_structured_outputs"]
