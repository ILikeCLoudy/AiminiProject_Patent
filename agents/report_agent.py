"""Report Agent - generates PDF reports with evidence and analysis."""
from __future__ import annotations

from typing import Any, Dict


class ReportAgent:
    """
    Agent responsible for generating PDF reports.

    Compiles patent evaluation results into a comprehensive PDF report
    with summary, scores, evidence, and methodology appendix.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Report Agent.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate PDF report.

        Args:
            state: Current state dictionary with all evaluation results

        Returns:
            Updated state with report path
        """
        # Report generation is handled by the langgraph _report_node
        # This agent is kept for compatibility but delegates to the orchestrator
        # to avoid duplicate PDF generation

        exec_meta = state.setdefault("exec_meta", {})
        exec_meta.setdefault("logs", []).append("ReportAgent: delegating to orchestrator _report_node")

        # Mark as completed only if not already done
        completed = exec_meta.setdefault("completed_nodes", [])
        if "REPORT" not in completed:
            completed.append("REPORT")

        return state


__all__ = ["ReportAgent"]
