"""LangGraph-based orchestrator for the patent intelligence pipeline."""
from __future__ import annotations

from typing import Any, Dict

from ingest_local import PATENT_COLLECTION, TRL_COLLECTION, run_ingestion
from ingestion.expand_with_api import expand_with_api
from report.compile_pdf import compile_report_pdf
from report.structured_outputs import write_structured_outputs
from retrieval.evidence_rag import gather_claims_evidence, gather_trl_evidence
from retrieval.synthesis_rag import generate_ps_e_summary
from scoring.scoring import WEIGHTS, compute_claim_score, decide_label, weighted_total

try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - optional dependency
    StateGraph = None  # type: ignore
    END = "END"  # type: ignore


class UnsupportedOrchestrator(RuntimeError):
    """Raised when langgraph is unavailable."""


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def _log(exec_meta: Dict[str, Any], message: str) -> None:
    exec_meta.setdefault("logs", []).append(message)


def _mark_completed(exec_meta: Dict[str, Any], node: str) -> None:
    completed = exec_meta.setdefault("completed_nodes", [])
    if node not in completed:
        completed.append(node)


def _ingest_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    result = run_ingestion(state)
    summary = result.get("summary", {})
    state.setdefault("metrics", {})["ingestion"] = summary
    embedded = summary.get("embedded", 0)
    skipped = summary.get("skipped", 0)
    _log(exec_meta, f"INGEST: embedded={embedded} skipped={skipped}")
    _mark_completed(exec_meta, "INGEST")
    return state


def _api_expand_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    payload = expand_with_api(state)
    if payload.get("ok"):
        summary = payload.get("summary", {})
        exec_meta.setdefault("api", {}).update(summary.get("meta", {}))
        _log(exec_meta, f"API_EXPAND: calls={summary.get('calls', 0)} cached={summary.get('cached', 0)}")
    else:
        exec_meta.setdefault("warnings", []).extend(payload.get("warnings", []))
        _log(exec_meta, "API_EXPAND: skipped (disabled or budget exhausted)")
    _mark_completed(exec_meta, "API_EXPAND")
    return state


def _trl_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    result = gather_trl_evidence(state)
    if not result.get("ok", True):
        exec_meta.setdefault("warnings", []).extend(result.get("warnings", []))
    exec_meta.setdefault("source_badges", {})["trl"] = state.get("evidence", {}).get("trl", {}).get(
        "source_badge", "Local RAG"
    )
    _log(exec_meta, "TRL: evidence gathered")
    _mark_completed(exec_meta, "TRL")
    return state


def _claims_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    result = gather_claims_evidence(state)
    if not result.get("ok", True):
        exec_meta.setdefault("warnings", []).extend(result.get("warnings", []))
    exec_meta.setdefault("source_badges", {})["claims"] = state.get("evidence", {}).get("claims", {}).get(
        "source_badge", "Local RAG"
    )
    _log(exec_meta, "CLAIMS: evidence gathered")
    _mark_completed(exec_meta, "CLAIMS")
    return state


def _join_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    join_meta = exec_meta.setdefault("join", {})
    if join_meta.get("completed"):
        _log(exec_meta, "JOIN: already completed, skipping duplicate invocation")
        return state

    evidence = state.get("evidence", {})
    aggregates = {
        "trl_snippets": len(evidence.get("trl", {}).get("snippets", [])),
        "claims_snippets": len(evidence.get("claims", {}).get("snippets", [])),
        "api_metrics": state.get("api", {}).get("metrics", {}),
    }
    state.setdefault("aggregates", {})["join"] = aggregates
    state.setdefault("synthesis", {})["ps_e_summary"] = generate_ps_e_summary(state)
    join_meta.update({"completed": True, "aggregates": aggregates})
    priority = state.get("routing", {}).get("priority", "unknown")
    _log(exec_meta, f"JOIN: merged evidence/API metrics (priority={priority})")
    _mark_completed(exec_meta, "JOIN")
    return state


def _score_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    score_meta = exec_meta.setdefault("score", {})
    if score_meta.get("completed"):
        _log(exec_meta, "SCORE: already completed, skipping duplicate invocation")
        return state

    scores = state.setdefault("scores", {})
    claims_ev = state.get("evidence", {}).get("claims", {})
    if claims_ev:
        num_independent = int(claims_ev.get("num_independent") or 0)
        avg_len_tokens = float(claims_ev.get("avg_len_tokens") or 0.0)
        scores["claim"] = compute_claim_score(num_independent, avg_len_tokens)

    flags: list[str] = []
    fto_penalty = scores.get("fto", 0.0)
    if isinstance(fto_penalty, (int, float)) and fto_penalty < 0:
        flags.append("FTO_risk")

    total_score = weighted_total(scores, WEIGHTS)
    label = decide_label(total_score, flags)

    decision = state.setdefault("decision", {})
    decision.update({"total": total_score, "label": label, "flags": flags})

    score_meta.update({"completed": True, "total": total_score, "label": label})
    _log(exec_meta, f"SCORE: total={total_score:.2f} label={label}")
    _mark_completed(exec_meta, "SCORE")
    return state


def _report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_meta = state.setdefault("exec_meta", {})
    decision = state.setdefault("decision", {})
    report_meta = exec_meta.setdefault("report", {})
    if decision.get("report_path"):
        _log(exec_meta, "REPORT: already generated, skipping duplicate invocation")
        return state

    write_structured_outputs(state.get("scores", {}), state.get("evidence", {}))

    report_payload = {
        "summary": decision,
        "scores": state.get("scores", {}),
        "evidence": state.get("evidence", {}),
        "api_metrics": state.get("api", {}).get("metrics", {}),
        "synthesis": state.get("synthesis", {}),
        "routing": state.get("routing", {}),
        "metadata": {
            "patent_collection": state.get("index", {}).get("patents_index", PATENT_COLLECTION),
            "trl_collection": state.get("index", {}).get("trl_ref_index", TRL_COLLECTION),
            "timestamp": exec_meta.get("ts"),
            "source_badges": exec_meta.get("source_badges", {}),
            "max_snippets_per_metric": state.get("config", {}).get("max_snippets_per_metric", 3),
        },
    }
    report_path = compile_report_pdf(report_payload)
    decision["report_path"] = report_path
    report_meta.update({"completed": True, "path": report_path})
    _log(exec_meta, f"REPORT: generated at {report_path}")
    _mark_completed(exec_meta, "REPORT")
    return state


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_langgraph(exec_meta: Dict[str, Any]) -> Any:
    """Create LangGraph workflow or raise if dependency missing."""
    if StateGraph is None:
        raise UnsupportedOrchestrator(
            "LangGraph is not installed. Install langgraph to use the orchestrator."
        )

    graph = StateGraph(dict)
    graph.set_entry_point("INGEST")

    graph.add_node("INGEST", _ingest_node)
    graph.add_node("API_EXPAND", _api_expand_node)
    graph.add_node("TRL", _trl_node)
    graph.add_node("CLAIMS", _claims_node)
    graph.add_node("JOIN", _join_node)
    graph.add_node("SCORE", _score_node)
    graph.add_node("REPORT", _report_node)

    graph.add_edge("INGEST", "API_EXPAND")
    graph.add_edge("API_EXPAND", "TRL")
    graph.add_edge("API_EXPAND", "CLAIMS")
    graph.add_edge("TRL", "JOIN")
    graph.add_edge("CLAIMS", "JOIN")
    graph.add_edge("JOIN", "SCORE")
    graph.add_edge("SCORE", "REPORT")
    graph.add_edge("REPORT", END)

    workflow = graph.compile()
    exec_meta.setdefault("orchestrator", "langgraph")
    return workflow


def run_pipeline(initial_state: Dict[str, Any], exec_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Execute pipeline via LangGraph workflow."""
    workflow = build_langgraph(exec_meta)
    return workflow.invoke(initial_state)


def run_pipeline_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    """Sequential fallback when langgraph is not available."""
    for node in (
        _ingest_node,
        _api_expand_node,
        _trl_node,
        _claims_node,
        _join_node,
        _score_node,
        _report_node,
    ):
        state = node(state)
    return state


__all__ = [
    "run_pipeline",
    "run_pipeline_fallback",
    "build_langgraph",
    "UnsupportedOrchestrator",
]
