"""Master agent orchestrator wired to the LangGraph pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from orchestrator.langgraph_runner import run_pipeline, UnsupportedOrchestrator


class MasterAgent:
    """Coordinates pipeline tasks for the patent analysis pipeline."""

    def __init__(self) -> None:
        self.pipeline_order: Sequence[str] = (
            "INGEST",
            "API_EXPAND",
            "TRL",
            "CLAIMS",
            "JOIN",
            "SCORE",
            "REPORT",
        )

    def plan(self, state: Dict[str, Any]) -> List[str]:
        return list(self.pipeline_order)

    def _prepare_exec_meta(self, state: Dict[str, Any]) -> Dict[str, Any]:
        exec_meta = state.setdefault("exec_meta", {})
        exec_meta.setdefault("logs", [])
        exec_meta.setdefault("warnings", [])
        exec_meta.setdefault("source_badges", {})
        exec_meta["plan"] = self.plan(state)

        try:
            tz = ZoneInfo("Asia/Seoul")
        except ZoneInfoNotFoundError:
            tz = None
        exec_meta["ts"] = datetime.now(tz).isoformat() if tz else datetime.now().isoformat()
        exec_meta.setdefault("version", "v0")
        exec_meta.setdefault("weights", state.get("config", {}).get("weights", "use_default"))
        exec_meta.setdefault("seed", state.get("config", {}).get("seed", 42))
        exec_meta.setdefault("cache_ttl_days", state.get("config", {}).get("cache_ttl_days", 30))
        return exec_meta

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        exec_meta = self._prepare_exec_meta(state)
        try:
            result_state = run_pipeline(state, exec_meta)
        except UnsupportedOrchestrator as exc:  # pragma: no cover - fallback when langgraph missing
            exec_meta["warnings"].append(str(exc))
            from orchestrator.langgraph_runner import run_pipeline_fallback

            result_state = run_pipeline_fallback(state)

        exec_meta.setdefault("logs", []).append("Pipeline execution completed.")
        return result_state


__all__ = ["MasterAgent"]
