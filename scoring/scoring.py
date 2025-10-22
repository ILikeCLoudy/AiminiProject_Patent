"""Scoring engine for the patent analysis pipeline."""
from __future__ import annotations

from typing import Dict, List, Optional

WEIGHTS: Dict[str, float] = {
    "trl": 0.20,
    "claim": 0.20,
    "legal": 0.08,
    "family": 0.10,
    "foreign": 0.08,
    "renewal": 0.06,
    "std": 0.04,
    "generality": 0.10,
    "originality": 0.10,
    "fto": 0.02,
}

CLAIM_OPT_RANGE: Dict[str, float] = {
    "indep_min": 1,
    "indep_max": 3,
    "len_min": 150,
    "len_max": 600,
}


def weighted_total(parts: Dict[str, Optional[float]], weights: Dict[str, float]) -> float:
    """Compute weighted total with redistribution for missing parts."""
    if not parts:
        return 0.0

    available = {key: value for key, value in parts.items() if value is not None}
    fto_penalty = 0.0
    if "fto" in available:
        raw_fto = available.pop("fto")
        if raw_fto is not None:
            fto_penalty = float(raw_fto)

    weighted_components = {
        key: float(value)
        for key, value in available.items()
        if weights.get(key, 0.0) > 0.0
    }

    weight_sum = sum(weights.get(key, 0.0) for key in weighted_components)
    base_score = 0.0
    if weight_sum > 0.0:
        base_score = sum(
            weighted_components[key] * (weights.get(key, 0.0) / weight_sum)
            for key in weighted_components
        )

    total_score = base_score + fto_penalty
    return max(0.0, min(100.0, total_score))


def decide_label(total: float, flags: Optional[List[str]] = None) -> str:
    """Assign a decision label based on total score and flags."""
    flags = flags or []
    clamped_total = max(0.0, min(100.0, total))

    if clamped_total >= 80.0:
        label = "A"
    elif clamped_total >= 70.0:
        label = "P"
    elif clamped_total >= 55.0:
        label = "M"
    else:
        label = "X"

    if "FTO_risk" in flags:
        demotions = {"A": "P", "P": "M", "M": "X", "X": "X"}
        label = demotions[label]

    return label


def compute_claim_score(num_independent: int, avg_len_tokens: float) -> Optional[float]:
    """Compute claim breadth score with U-shaped penalty based on independent count and length."""
    if num_independent <= 0:
        return None

    score = 85.0
    indep_min = CLAIM_OPT_RANGE["indep_min"]
    indep_max = CLAIM_OPT_RANGE["indep_max"]

    if num_independent < indep_min:
        score -= (indep_min - num_independent) * 15.0
    elif num_independent > indep_max:
        score -= (num_independent - indep_max) * 7.5

    len_min = CLAIM_OPT_RANGE["len_min"]
    len_max = CLAIM_OPT_RANGE["len_max"]

    if avg_len_tokens < len_min:
        deficit = (len_min - avg_len_tokens) / max(len_min, 1)
        score -= deficit * 25.0
    elif avg_len_tokens > len_max:
        overage = (avg_len_tokens - len_max) / max(len_max, 1)
        score -= overage * 25.0

    return max(0.0, min(100.0, score))


__all__ = ["WEIGHTS", "CLAIM_OPT_RANGE", "weighted_total", "decide_label", "compute_claim_score"]
