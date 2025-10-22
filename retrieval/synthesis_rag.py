"""Synthesis RAG utilities for concise patent summaries."""
from __future__ import annotations

from typing import Any, Dict, List


def _pick_snippet_text(snippets: List[Dict[str, Any]]) -> str:
    if not snippets:
        return ""
    best = max(snippets, key=lambda item: (item.get("score_trace", {}).get("hybrid", 0.0), len(item.get("text", ""))))
    return best.get("text", "")


def generate_ps_e_summary(state: Dict[str, Any]) -> str:
    """Generate a Problem-Solution-Evidence summary from collected signals."""
    config = state.get("config", {})
    keywords = config.get("keywords", []) or []
    keyword_text = ", ".join(keywords[:3]) if keywords else "edge AI execution"

    claims = state.get("evidence", {}).get("claims", {})
    trl = state.get("evidence", {}).get("trl", {})
    metrics = state.get("api", {}).get("metrics", {})

    claim_snippet = _pick_snippet_text(claims.get("snippets", []))
    trl_level = trl.get("level")
    citations = metrics.get("forward_citations_5y", 0)

    problem_sentence = f"Problem: identify enforceable claims for {keyword_text} deployments."
    solution_sentence = (
        f"Solution: independent claims highlight configurations such as {claim_snippet[:120]}..."
        if claim_snippet
        else "Solution: independent claims outline edge inference orchestration with configurable modules."
    )
    evidence_sentence = (
        f"Evidence: TRL estimate {trl_level or 'N/A'} with {citations} forward citations supports readiness."
    )
    return " ".join([problem_sentence, solution_sentence, evidence_sentence])


__all__ = ["generate_ps_e_summary"]
