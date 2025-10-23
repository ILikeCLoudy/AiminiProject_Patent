"""Edge Adapter Agent - evaluates Edge AI/on-device suitability."""
from __future__ import annotations

from typing import Any, Dict, List


class EdgeAdapterAgent:
    """
    Agent responsible for evaluating Edge AI/on-device compatibility.

    Extracts and validates latency, power, memory, and accuracy metrics
    against device thresholds.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Edge Adapter Agent.

        Args:
            config: Configuration dictionary with edge_thresholds
        """
        self.config = config
        self.thresholds = config.get("edge_thresholds", {})

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate Edge AI suitability and flag constraint violations.

        Args:
            state: Current state dictionary with evidence

        Returns:
            Updated state with edge adapter scores and flags
        """
        # Extract edge metrics from evidence
        evidence = state.get("evidence", {})
        edge_metrics = evidence.get("edge_performance", {})

        # Evaluate against thresholds
        adapter_scores = {}
        flags = []

        # Latency check
        latency_ms = edge_metrics.get("latency_ms")
        if latency_ms is not None:
            threshold = self.thresholds.get("latency_ms", 50)
            adapter_scores["latency_score"] = self._score_latency(latency_ms, threshold)
            if latency_ms > threshold:
                flags.append(f"LATENCY_EXCEEDS_THRESHOLD: {latency_ms}ms > {threshold}ms")

        # Power check
        power_mw = edge_metrics.get("power_mw")
        if power_mw is not None:
            threshold = self.thresholds.get("power_mw", 600)
            adapter_scores["power_score"] = self._score_power(power_mw, threshold)
            if power_mw > threshold:
                flags.append(f"POWER_EXCEEDS_THRESHOLD: {power_mw}mW > {threshold}mW")

        # Memory check
        memory_mb = edge_metrics.get("memory_mb")
        if memory_mb is not None:
            threshold = self.thresholds.get("memory_mb", 256)
            adapter_scores["memory_score"] = self._score_memory(memory_mb, threshold)
            if memory_mb > threshold:
                flags.append(f"MEMORY_EXCEEDS_THRESHOLD: {memory_mb}MB > {threshold}MB")

        # Accuracy delta check
        accuracy_delta = edge_metrics.get("accuracy_delta")
        if accuracy_delta is not None:
            adapter_scores["accuracy_score"] = self._score_accuracy_delta(accuracy_delta)
            if accuracy_delta < -5.0:  # More than 5% accuracy drop
                flags.append(f"ACCURACY_DEGRADATION: {accuracy_delta}%")

        # Update state
        state.setdefault("adapter_scores", {}).update(adapter_scores)
        state.setdefault("decision", {}).setdefault("flags", []).extend(flags)

        state.setdefault("exec_meta", {}).setdefault("completed_nodes", []).append("EDGE_ADAPTER")

        return state

    def _score_latency(self, value: float, threshold: float) -> float:
        """Score latency (lower is better): 100 = meets threshold."""
        if value <= threshold * 0.5:
            return 100.0
        elif value <= threshold:
            return 80.0 - ((value / threshold - 0.5) * 60)  # Linear 80-20
        else:
            return max(0.0, 20.0 - ((value / threshold - 1.0) * 20))

    def _score_power(self, value: float, threshold: float) -> float:
        """Score power consumption (lower is better)."""
        return self._score_latency(value, threshold)  # Same logic

    def _score_memory(self, value: float, threshold: float) -> float:
        """Score memory usage (lower is better)."""
        return self._score_latency(value, threshold)  # Same logic

    def _score_accuracy_delta(self, delta: float) -> float:
        """Score accuracy delta (0 is ideal, negative is bad)."""
        if delta >= 0:
            return 100.0  # No degradation
        elif delta >= -2.0:
            return 80.0 + delta * 10  # -2% = 60pts
        elif delta >= -5.0:
            return 60.0 + (delta + 2.0) * 10  # -5% = 30pts
        else:
            return max(0.0, 30.0 + (delta + 5.0) * 6)  # Steeper penalty


__all__ = ["EdgeAdapterAgent"]
