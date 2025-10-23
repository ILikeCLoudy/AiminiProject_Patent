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
        exec_meta = state.setdefault("exec_meta", {})

        # Extract edge metrics from state performance
        performance = state.get("performance", {})
        edge_metrics_raw = performance.get("metrics", {})

        # Convert nested dict structure to flat values
        edge_metrics = {}
        for key, val in edge_metrics_raw.items():
            if isinstance(val, dict):
                edge_metrics[key] = val.get("value")
            else:
                edge_metrics[key] = val

        # Priority 4: LLM inference if no metrics found
        if not edge_metrics or all(v is None for v in edge_metrics.values()):
            if self.config.get("llm", {}).get("use_tool_calling", False):
                try:
                    edge_metrics = self._llm_infer_performance(state)
                    exec_meta.setdefault("logs", []).append("Edge: LLM inference used for performance estimation")
                except Exception as e:
                    exec_meta.setdefault("warnings", []).append(f"Edge LLM inference failed: {str(e)}")

        # Priority 5: Mark as N/A if still no data
        if not edge_metrics or all(v is None for v in edge_metrics.values()):
            exec_meta.setdefault("logs", []).append("Edge: No performance data available (N/A)")
            state["performance"]["status"] = "not_available"
            state["performance"]["reason"] = "No benchmark data found in public sources"
            return state

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

    def _llm_infer_performance(self, state: Dict[str, Any]) -> Dict[str, float]:
        """
        Use LLM to infer edge performance metrics from patent description.

        Returns:
            Dictionary with inferred metrics (latency_ms, power_mw, memory_mb, accuracy_delta)
        """
        try:
            import os
            from openai import OpenAI
        except ImportError:
            return {}

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {}

        # Get patent info
        metas = state.get("inputs", {}).get("metas", [])
        if not metas:
            return {}

        patent_meta = metas[0]
        doc_id = patent_meta.get("doc_id", "")
        title = patent_meta.get("title", "")
        notes = patent_meta.get("notes", "")

        # Get evidence snippets
        evidence = state.get("evidence", {})
        trl_snippets = evidence.get("trl", {}).get("snippets", [])
        snippet_texts = [s.get("text", "")[:200] for s in trl_snippets[:2]]

        prompt = f"""You are an edge AI performance expert. Based on the patent information below, estimate the edge device performance metrics.

Patent: {doc_id}
Title: {title}
Notes: {notes}

Evidence snippets:
{chr(10).join(snippet_texts) if snippet_texts else "No technical details available"}

Estimate the following metrics for edge device deployment:
1. Inference latency (ms): Typical latency for one inference
2. Power consumption (mW): Power draw during inference
3. Memory footprint (MB): Model size in memory
4. Accuracy delta (%): Accuracy change vs. baseline (negative = degradation)

Provide realistic estimates based on typical edge AI implementations. If unsure, provide conservative estimates.

Respond in JSON format:
{{
  "latency_ms": <number>,
  "power_mw": <number>,
  "memory_mb": <number>,
  "accuracy_delta": <number>,
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>"
}}
"""

        try:
            client = OpenAI(api_key=api_key, timeout=30)
            response = client.chat.completions.create(
                model=self.config.get("llm", {}).get("model", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            return {
                "latency_ms": result.get("latency_ms"),
                "power_mw": result.get("power_mw"),
                "memory_mb": result.get("memory_mb"),
                "accuracy_delta": result.get("accuracy_delta")
            }

        except Exception:
            return {}


__all__ = ["EdgeAdapterAgent"]
