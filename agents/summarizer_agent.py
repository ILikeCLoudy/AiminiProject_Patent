"""Summarizer Agent - generates Problem-Solution-Evidence summaries using LLM."""
from __future__ import annotations

from typing import Any, Dict, Optional


class SummarizerAgent:
    """
    Agent responsible for generating patent summaries.

    Uses LLM to create concise 3-sentence Problem-Solution-Evidence (P-S-E) summaries
    based on patent text, TRL evidence, and other metadata.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Summarizer Agent.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._llm_client: Optional[Any] = None

    def _get_llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            try:
                from llm.client import get_llm_client

                self._llm_client = get_llm_client(self.config)
            except Exception as e:
                # Fallback to template-based summary
                self._llm_client = None
        return self._llm_client

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate P-S-E summary for the patent.

        Args:
            state: Current state dictionary with evidence

        Returns:
            Updated state with summary
        """
        # Extract evidence for context
        evidence = state.get("evidence", {})
        trl_data = evidence.get("trl", {})
        claims_data = evidence.get("claims", {})
        api_meta = state.get("api_meta", [])

        # Build context
        context = {
            "trl_level": trl_data.get("level"),
            "citations": self._get_metric_value(api_meta, "CITATIONS_TOTAL"),
            "family_size": self._get_metric_value(api_meta, "FAMILY_SIZE"),
        }

        # Collect patent text from snippets
        patent_text_parts = []
        for snippet in trl_data.get("snippets", [])[:3]:
            patent_text_parts.append(snippet.get("text", ""))
        for snippet in claims_data.get("snippets", [])[:2]:
            patent_text_parts.append(snippet.get("text", ""))

        patent_text = "\n\n".join(patent_text_parts)[:2000]

        # Generate summary
        llm_client = self._get_llm_client()
        if llm_client and patent_text:
            try:
                summary = llm_client.generate_summary(patent_text, context)
            except Exception:
                summary = self._fallback_summary(context)
        else:
            summary = self._fallback_summary(context)

        # Update state
        state.setdefault("summaries", {})["pse"] = summary
        state.setdefault("exec_meta", {}).setdefault("completed_nodes", []).append("SUMMARIZE")

        return state

    def _get_metric_value(self, api_meta: list, metric_key: str) -> Optional[Any]:
        """Extract metric value from API metadata."""
        for record in api_meta:
            if record.get("metric_key") == metric_key and record.get("chosen"):
                return record.get("value")
        return None

    def _fallback_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based summary as fallback."""
        trl = context.get("trl_level", "N/A")
        citations = context.get("citations", 0)
        family = context.get("family_size", 1)

        problem = "Problem: Address technical challenges in Edge AI/on-device deployment with novel approach."
        solution = f"Solution: Implement innovative method with {family} family member(s) across jurisdictions."
        evidence = f"Evidence: TRL estimate {trl}, {citations} forward citations demonstrate technical validation."

        return f"{problem} {solution} {evidence}"


__all__ = ["SummarizerAgent"]
