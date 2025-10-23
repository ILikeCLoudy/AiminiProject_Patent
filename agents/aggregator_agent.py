"""Aggregator Agent - computes weighted total and assigns A/P/M/X labels."""
from __future__ import annotations

from typing import Any, Dict


class AggregatorAgent:
    """
    Agent responsible for aggregating scores and assigning decision labels.

    Computes weighted total from core scores and adapter scores,
    then assigns Adopt/Prototype/Monitor/Archive (A/P/M/X) label.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Aggregator Agent.

        Args:
            config: Configuration dictionary with weights
        """
        self.config = config
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict[str, float]:
        """Load scoring weights from config."""
        from scoring.scoring import WEIGHTS

        weights_cfg = self.config.get("weights")
        if weights_cfg == "use_default" or not weights_cfg:
            return WEIGHTS
        elif isinstance(weights_cfg, dict):
            return weights_cfg
        else:
            return WEIGHTS

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate scores and assign decision label.

        Args:
            state: Current state dictionary with scores

        Returns:
            Updated state with total score and label
        """
        from scoring.scoring import weighted_total, decide_label

        # Collect scores
        scores = state.get("scores", {})
        flags = state.get("decision", {}).get("flags", [])

        # Compute weighted total
        total, details = weighted_total(scores, self.weights, return_details=True)

        # Assign label
        label = decide_label(total, flags)

        # Update state
        decision = state.setdefault("decision", {})
        decision["total"] = total
        decision["label"] = label
        decision["score_details"] = details

        state.setdefault("exec_meta", {}).setdefault("completed_nodes", []).append("AGGREGATE")

        return state


__all__ = ["AggregatorAgent"]
