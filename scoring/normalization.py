"""Threshold-based normalization for patent metrics."""
from __future__ import annotations

from typing import Any, Dict, Optional


# Fixed thresholds for percentile-to-5-point scale conversion
# Based on typical patent metric distributions in Edge AI/On-device domain
NORMALIZATION_THRESHOLDS = {
    "CITATIONS_TOTAL": {
        # Citations: 0-5=1pt, 6-15=2pt, 16-30=3pt, 31-60=4pt, 61+=5pt
        "thresholds": [0, 6, 16, 31, 61],
        "labels": [1, 2, 3, 4, 5],
        "description": "Forward citations (5-year window)",
    },
    "FAMILY_SIZE": {
        # Family: 1=1pt, 2-3=2pt, 4-6=3pt, 7-12=4pt, 13+=5pt
        "thresholds": [1, 2, 4, 7, 13],
        "labels": [1, 2, 3, 4, 5],
        "description": "Patent family size (distinct jurisdictions)",
    },
    "COUNTRIES": {
        # Countries: 1=1pt, 2=2pt, 3-4=3pt, 5-8=4pt, 9+=5pt
        "thresholds": [1, 2, 3, 5, 9],
        "labels": [1, 2, 3, 4, 5],
        "description": "Number of countries in family",
    },
    "HHI": {
        # HHI (lower = more diverse): >5000=1pt, 2500-5000=2pt, 1500-2500=3pt, 800-1500=4pt, <800=5pt
        "thresholds": [800, 1500, 2500, 5000, 10000],
        "labels": [5, 4, 3, 2, 1],  # Reversed: lower HHI = better
        "description": "Herfindahl-Hirschman Index (market concentration)",
    },
    "GENERALITY": {
        # Generality: 0-20=1pt, 21-40=2pt, 41-60=3pt, 61-80=4pt, 81-100=5pt
        "thresholds": [0, 21, 41, 61, 81],
        "labels": [1, 2, 3, 4, 5],
        "description": "Technology generality index (0-100)",
    },
    "ORIGINALITY": {
        # Originality: 0-30=1pt, 31-50=2pt, 51-70=3pt, 71-85=4pt, 86-100=5pt
        "thresholds": [0, 31, 51, 71, 86],
        "labels": [1, 2, 3, 4, 5],
        "description": "Technology originality index (0-100)",
    },
    "AGE_YEARS": {
        # Age: >15yr=1pt, 10-15=2pt, 5-10=3pt, 2-5=4pt, <2=5pt
        "thresholds": [2, 5, 10, 15, 100],
        "labels": [5, 4, 3, 2, 1],  # Reversed: newer = better
        "description": "Patent age in years",
    },
    "TRL": {
        # TRL: 1-3=1pt, 4-5=2pt, 6=3pt, 7-8=4pt, 9=5pt
        "thresholds": [1, 4, 6, 7, 9],
        "labels": [1, 2, 3, 4, 5],
        "description": "Technology Readiness Level (1-9 NASA scale)",
    },
}


def normalize_to_5point(
    value: Any,
    metric_key: str,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Normalize a metric value to 1-5 point scale using fixed thresholds.

    Args:
        value: Raw metric value (int, float, or list)
        metric_key: Metric identifier (e.g., "CITATIONS_TOTAL")
        thresholds: Custom thresholds (defaults to NORMALIZATION_THRESHOLDS)

    Returns:
        Normalized score (1-5) or None if value is invalid
    """
    if value is None:
        return None

    thresholds = thresholds or NORMALIZATION_THRESHOLDS
    config = thresholds.get(metric_key)
    if not config:
        # No normalization rule: return None
        return None

    # Handle list values (e.g., COUNTRIES)
    if isinstance(value, list):
        value = len(value)

    # Convert to numeric
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    # Apply threshold rules
    threshold_values = config["thresholds"]
    labels = config["labels"]

    for i, threshold in enumerate(threshold_values):
        if numeric_value < threshold:
            return labels[max(0, i - 1)] if i > 0 else labels[0]

    # Value exceeds all thresholds: return highest label
    return labels[-1]


def normalize_score_100pt(
    value_5pt: Optional[int],
    min_score: float = 0.0,
    max_score: float = 100.0,
) -> Optional[float]:
    """
    Convert 5-point scale to 100-point scale.

    Args:
        value_5pt: Normalized 1-5 point value
        min_score: Minimum score (default 0)
        max_score: Maximum score (default 100)

    Returns:
        Score on 100-point scale or None
    """
    if value_5pt is None:
        return None

    if value_5pt < 1 or value_5pt > 5:
        return None

    # Linear mapping: 1->20, 2->40, 3->60, 4->80, 5->100
    step = (max_score - min_score) / 5
    return min_score + (value_5pt * step)


def get_normalized_metrics(
    raw_metrics: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Normalize all metrics to 5-point and 100-point scales.

    Args:
        raw_metrics: Dictionary of raw metric values
        thresholds: Custom thresholds (optional)

    Returns:
        Dictionary with normalized values and metadata
    """
    thresholds = thresholds or NORMALIZATION_THRESHOLDS
    normalized = {}

    for metric_key, raw_value in raw_metrics.items():
        if metric_key not in thresholds:
            # Pass through non-normalized metrics
            normalized[metric_key] = {
                "raw": raw_value,
                "normalized_5pt": None,
                "normalized_100pt": None,
                "method": "none",
            }
            continue

        value_5pt = normalize_to_5point(raw_value, metric_key, thresholds)
        value_100pt = normalize_score_100pt(value_5pt) if value_5pt else None

        normalized[metric_key] = {
            "raw": raw_value,
            "normalized_5pt": value_5pt,
            "normalized_100pt": value_100pt,
            "method": "fixed_threshold",
            "config": thresholds[metric_key]["description"],
        }

    return normalized


def apply_cohort_adjustment(
    normalized_score: float,
    cpc_class: str,
    publication_year: int,
    cohort_stats: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Apply CPC×Year cohort adjustment (placeholder for future enhancement).

    Currently returns the input score unchanged.
    In future: load cohort statistics and compute percentile ranks.

    Args:
        normalized_score: Score from fixed threshold normalization
        cpc_class: CPC classification (e.g., "G06N")
        publication_year: Year of publication
        cohort_stats: Cohort statistics (optional, for future use)

    Returns:
        Adjusted score
    """
    # TODO: Implement cohort-based percentile adjustment
    # For now, return the input score unchanged
    return normalized_score


__all__ = [
    "NORMALIZATION_THRESHOLDS",
    "normalize_to_5point",
    "normalize_score_100pt",
    "get_normalized_metrics",
    "apply_cohort_adjustment",
]
