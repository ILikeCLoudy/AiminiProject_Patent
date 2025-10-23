"""Core Scoring Agent - computes normalized scores for core metrics."""
from __future__ import annotations

from typing import Any, Dict


class CoreScoringAgent:
    """
    Agent responsible for computing core metric scores.

    Applies fixed-threshold normalization to convert raw metrics
    to 1-5 point scale, then to 100-point scale.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Core Scoring Agent.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute normalized scores for core metrics.

        Args:
            state: Current state dictionary with API metrics

        Returns:
            Updated state with normalized scores
        """
        from scoring.normalization import get_normalized_metrics

        # Extract raw metrics from API metadata
        api_meta = state.get("api_meta", [])
        raw_metrics = {}
        for record in api_meta:
            if record.get("chosen"):
                metric_key = record.get("metric_key")
                value = record.get("value")
                if metric_key and value is not None:
                    raw_metrics[metric_key] = value

        # Add TRL from evidence
        evidence = state.get("evidence", {})
        trl_level = evidence.get("trl", {}).get("level")
        if trl_level is not None:
            raw_metrics["TRL"] = trl_level

        # Normalize metrics
        normalized = get_normalized_metrics(raw_metrics)

        # Store in state
        state.setdefault("core_scores", {})
        for metric_key, data in normalized.items():
            state["core_scores"][metric_key] = {
                "raw": data["raw"],
                "normalized_5pt": data["normalized_5pt"],
                "normalized_100pt": data["normalized_100pt"],
                "method": data["method"],
            }

        state.setdefault("exec_meta", {}).setdefault("completed_nodes", []).append("CORE_SCORE")

        return state


__all__ = ["CoreScoringAgent"]
