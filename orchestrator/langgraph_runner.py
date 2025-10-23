"""LangGraph-based orchestrator for the patent intelligence pipeline."""
from __future__ import annotations

from typing import Any, Dict, List

from ingest_local import PATENT_COLLECTION, TRL_COLLECTION, run_ingestion
from ingestion.expand_with_api import expand_with_api
from adapters.api_clients import METRIC_KEYS
from report.compile_pdf import compile_report_pdf
from report.structured_outputs import write_structured_outputs
from retrieval.edge_metrics import extract_edge_performance
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
    summary = payload.get("summary", {}) or {}
    warnings = payload.get("warnings", [])
    api_meta = exec_meta.setdefault("api", {})
    api_meta.update(
        {
            "calls": summary.get("calls", api_meta.get("calls", 0)),
            "cached": summary.get("cached", api_meta.get("cached", 0)),
            "batches": summary.get("batches", api_meta.get("batches", 0)),
            "collected_keys": summary.get("collected_keys", []),
            "missing_keys": summary.get("missing_keys", []),
            "ok_count": summary.get("ok_count", 0),
        }
    )
    prom = exec_meta.setdefault("prometheus", {})
    prom["api_meta_ok_total"] = prom.get("api_meta_ok_total", 0) + summary.get("ok_count", 0)
    prom["api_meta_missing_total"] = prom.get("api_meta_missing_total", 0) + len(summary.get("missing_keys", []))
    if any(row.get("status") == "blocked_domain" for row in (state.get("api_meta", []) or [])):
        prom["api_domain_blocked_total"] = prom.get("api_domain_blocked_total", 0) + 1
    if warnings:
        exec_meta.setdefault("warnings", []).extend(warnings)
    missing_reason = warnings[0] if warnings else "ok"
    log_line = (
        f"API_EXPAND: calls={summary.get('calls', 0)} cached={summary.get('cached', 0)} "
        f"batches={summary.get('batches', 0)} ok={summary.get('ok_count', 0)}/{summary.get('total_metrics', 0)} "
        f"missing={','.join(summary.get('missing_keys', [])) or 'none'} reason={missing_reason}"
    )
    _log(exec_meta, log_line)
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

    config = state.get("config", {})
    evidence = state.get("evidence", {})
    api_rows = state.get("api", {}).get("rows", [])
    performance_metrics = extract_edge_performance(state)

    # Tavily integration for SEP/standard evidence
    tavily_results = []
    if config.get("tavily", {}).get("enabled", False):
        try:
            from adapters.link_finder_tavily import search_official_links

            # Search for SEP declarations if indicated
            sep_declared = any(
                row.get("metric_key") == "SEP_INDICATION"
                and row.get("value") in ("declared", True)
                for row in api_rows
            )

            if sep_declared:
                doc_id = state.get("inputs", {}).get("metas", [{}])[0].get("doc_id", "unknown")
                query = f"{doc_id} SEP declaration ETSI 3GPP"
                tavily_results = search_official_links(config, exec_meta, query)
                _log(exec_meta, f"JOIN: Tavily search returned {len(tavily_results)} links")
        except Exception as e:
            _log(exec_meta, f"JOIN: Tavily search failed: {str(e)}")

    aggregates = {
        "trl_snippets": len(evidence.get("trl", {}).get("snippets", [])),
        "claims_snippets": len(evidence.get("claims", {}).get("snippets", [])),
        "api_rows": api_rows,
        "api_missing": state.get("api_missing_flags", []),
        "performance": performance_metrics,
        "tavily_links": tavily_results,
    }
    state.setdefault("aggregates", {})["join"] = aggregates

    # Use Summarizer Agent for LLM-based summary
    try:
        from agents.summarizer_agent import SummarizerAgent
        agent = SummarizerAgent(config)
        state = agent.run(state)
        ps_e_summary = state.get("summaries", {}).get("pse", "")
        _log(exec_meta, "JOIN: Generated LLM-based P-S-E summary")
    except Exception as e:
        # Fallback to template-based summary
        ps_e_summary = generate_ps_e_summary(state)
        _log(exec_meta, f"JOIN: LLM summary failed, using template: {str(e)}")

    state.setdefault("synthesis", {})["ps_e_summary"] = ps_e_summary
    api_metrics_entry = state.setdefault("evidence", {}).setdefault("api_metrics", {})
    api_metrics_entry["rows"] = api_rows
    api_metrics_entry["missing"] = state.get("api_missing_flags", [])
    state.setdefault("performance", {})["metrics"] = performance_metrics
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

    config = state.get("config", {})
    scores = state.setdefault("scores", {})

    # Compute claim score (existing logic)
    claims_ev = state.get("evidence", {}).get("claims", {})
    if claims_ev:
        num_independent = int(claims_ev.get("num_independent") or 0)
        avg_len_tokens = float(claims_ev.get("avg_len_tokens") or 0.0)
        scores["claim"] = compute_claim_score(num_independent, avg_len_tokens)

    # Core Scoring Agent - apply normalization
    try:
        from agents.core_scoring_agent import CoreScoringAgent
        agent = CoreScoringAgent(config)
        state = agent.run(state)
        _log(exec_meta, "SCORE: Applied normalization via CoreScoringAgent")
    except Exception as e:
        _log(exec_meta, f"SCORE: CoreScoringAgent failed: {str(e)}")

    # Edge Adapter Agent - evaluate edge suitability
    try:
        from agents.edge_adapter_agent import EdgeAdapterAgent
        agent = EdgeAdapterAgent(config)
        state = agent.run(state)
        _log(exec_meta, "SCORE: Evaluated edge suitability via EdgeAdapterAgent")
    except Exception as e:
        _log(exec_meta, f"SCORE: EdgeAdapterAgent failed: {str(e)}")

    # Legacy flag logic (keep for compatibility)
    api_rows = state.get("api", {}).get("rows", []) or []
    chosen_api = {row["metric_key"]: row for row in api_rows if row.get("chosen")}

    flags: list[str] = []
    litigation_row = chosen_api.get("LITIGATION_FLAG")
    if not litigation_row or litigation_row.get("status") != "ok":
        scores.setdefault("fto", -10.0)
        flags.append("FTO_risk")
    sep_row = chosen_api.get("SEP_INDICATION")
    if not sep_row or sep_row.get("status") != "ok":
        scores["std"] = min(scores.get("std", 30.0), 45.0)

    # Merge flags from Edge Adapter
    decision_flags = state.get("decision", {}).get("flags", [])
    flags.extend(decision_flags)

    # Aggregator Agent - compute total and assign label
    try:
        from agents.aggregator_agent import AggregatorAgent
        agent = AggregatorAgent(config)
        state = agent.run(state)
        total_score = state.get("decision", {}).get("total", 0.0)
        label = state.get("decision", {}).get("label", "X")
        weight_details = state.get("decision", {}).get("score_details", {})
        _log(exec_meta, "SCORE: Aggregated scores via AggregatorAgent")
    except Exception as e:
        # Fallback to legacy scoring
        total_score, weight_details = weighted_total(scores, WEIGHTS, return_details=True)
        label = decide_label(total_score, flags)
        decision = state.setdefault("decision", {})
        decision.update({"total": total_score, "label": label, "flags": flags})
        _log(exec_meta, f"SCORE: AggregatorAgent failed, using legacy: {str(e)}")

    decision = state.setdefault("decision", {})
    decision["weights_meta"] = weight_details
    decision["weights_redistributed"] = weight_details.get("redistributed", False)

    score_meta.update(
        {
            "completed": True,
            "total": total_score,
            "label": label,
            "weights": weight_details.get("contributions", {}),
            "redistributed": weight_details.get("redistributed", False),
            "missing_weights": weight_details.get("missing_keys", []),
        }
    )
    state.setdefault("evidence", {}).setdefault("score", {}).update(
        {
            "weights": weight_details.get("contributions", {}),
            "weights_redistributed": weight_details.get("redistributed", False),
            "missing_weights": weight_details.get("missing_keys", []),
        }
    )
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

    api_rows = state.get("api", {}).get("rows", [])
    chosen_api = {row["metric_key"]: row for row in api_rows if row.get("chosen")}
    countries_value = chosen_api.get("COUNTRIES", {}).get("value")
    if isinstance(countries_value, str):
        country_count = len({part.strip() for part in countries_value.split(",") if part.strip()})
    elif isinstance(countries_value, list):
        country_count = len(countries_value)
    else:
        country_count = 0
    family_size = chosen_api.get("FAMILY_SIZE", {}).get("value")
    citations_total = chosen_api.get("CITATIONS_TOTAL", {}).get("value")
    ingestion_docs = state.get("metrics", {}).get("ingestion", {}).get("documents", [])
    doc_count = len(ingestion_docs) if ingestion_docs else len(state.get("inputs", {}).get("pdfs", []))
    missing_keys = state.get("api_missing_flags", [])
    total_metrics = len(METRIC_KEYS)
    ok_metrics = total_metrics - len(missing_keys)
    missing_ratio = (total_metrics - ok_metrics) / total_metrics if total_metrics else 0.0
    score_total = decision.get("total")
    label = decision.get("label", "N/A")
    scores = state.get("scores", {})
    trl_score = scores.get("trl")
    claim_score = scores.get("claim")

    config = state.get("config", {})
    keywords = ", ".join(config.get("keywords", []))
    cpc_codes = ", ".join(config.get("cpc", []))
    period = config.get("period", {})
    routing_priority = state.get("routing", {}).get("priority", "N/A")
    performance_metrics = state.get("performance", {}).get("metrics", {})

    conclusion = f"Label {label}: TRL {trl_score or 'N/A'} / Claim {claim_score or 'N/A'}"
    core_reasons: List[str] = []
    if trl_score is not None:
        core_reasons.append(f"TRL readiness score {trl_score:.1f}")
    if claim_score is not None:
        core_reasons.append(f"Claim breadth score {claim_score:.1f}")
    if not core_reasons:
        core_reasons.append("근거 스니펫 부족")

    summary_card = {
        "conclusion": conclusion,
        "reasons": core_reasons[:2],
        "purpose_scope": {
            "purpose": "Edge AI 특허 기술성·시장성 평가",
            "scope": {
                "keywords": keywords,
                "cpc": cpc_codes,
                "period": f"{period.get('from', 'N/A')} ~ {period.get('to', 'N/A')}",
                "target_market": routing_priority,
            },
        },
        "top_line": {
            "documents": doc_count,
            "family_size": family_size,
            "country_count": country_count,
            "label": label,
        },
        "actions": [
            {"action": "FTO 상세 검토", "owner": "IP 팀", "due": "+7d", "note": "리스크 플래그 대응"},
            {"action": "표준 연계 확인", "owner": "표준화 팀", "due": "+14d", "note": "SEP 선언 여부 검증"},
            {"action": "데이터 보완", "owner": "AI 전략팀", "due": "+21d", "note": f"결측 지표 {len(missing_keys)}개 채우기"},
        ],
        "risks": [
            {"item": "FTO_risk" if "FTO_risk" in decision.get("flags", []) else "데이터 결측", "impact": "출시 전 법률/데이터 보강 필요"},
            {"item": "데이터 결측" if missing_keys else "표준 연계 미확인", "impact": f"{ok_metrics}/{total_metrics} 지표만 확보"},
        ],
        "trust_meta": {
            "contribution": decision.get("weights_meta", {}).get("contributions", {}),
            "missing_ratio": missing_ratio,
            "timestamp": exec_meta.get("ts"),
            "policy_version": exec_meta.get("version", "v0"),
        },
    }

    main_body = {
        "scope_method": {
            "scope": summary_card["purpose_scope"]["scope"],
            "method": {
                "normalisation": "퍼센타일 → 5점(설계 예정)",
                "weights": "기술/시장/경쟁 가중 합산",
                "label_rule": "A/P/M/X 총점 및 FTO 보수 규칙",
            },
        },
        "dataset": {
            "documents": doc_count,
            "family_size": family_size,
            "countries": countries_value,
            "quality": {
                "missing_metrics": missing_keys,
                "translation_flags": "N/A",
                "dedup": "N/A",
            },
        },
        "core_metrics": {
            "citations_total": citations_total,
            "family": family_size,
            "countries": countries_value,
            "legal_status": chosen_api.get("RENEWAL_STATUS", {}).get("value"),
            "trl_score": trl_score,
            "claim_score": claim_score,
        },
        "edge_fitness": performance_metrics,
        "competitive": {
            "hhi": chosen_api.get("HHI", {}).get("value"),
            "generality": chosen_api.get("GENERALITY", {}).get("value"),
            "originality": chosen_api.get("ORIGINALITY", {}).get("value"),
            "sep": chosen_api.get("SEP_INDICATION", {}).get("value"),
        },
        "risk_profile": {
            "flags": decision.get("flags", []),
            "data_gaps": missing_keys,
        },
        "ranking": {
            "total_score": score_total,
            "label": label,
            "distribution": {"A": 0, "P": 0, "M": 0, "X": 1 if label == "X" else 0},
        },
        "candidate_cards": [
            {
                "title": state.get("inputs", {}).get("metas", [{}])[0].get("doc_id", "N/A"),
                "family": family_size,
                "owner": state.get("inputs", {}).get("metas", [{}])[0].get("title", "N/A"),
                "jurisdictions": countries_value,
                "decision": "Monitor" if label in {"M", "X"} else "Adopt",
                "signals": core_reasons[:3],
                "risks": summary_card["risks"],
            }
        ],
        "conclusion": core_reasons,
    }

    references: List[Dict[str, Any]] = []
    seen_refs = set()
    for row in api_rows:
        url = row.get("source_url")
        if url and url not in seen_refs:
            seen_refs.add(url)
            references.append({"source": row.get("source_name"), "url": url})
    for doc in state.get("inputs", {}).get("pdfs", []):
        if doc and doc not in seen_refs:
            seen_refs.add(doc)
            references.append({"source": "Local PDF", "url": doc})

    appendix = {
        "purpose": summary_card["purpose_scope"]["purpose"],
        "pipeline": "PDF → Chunk → Evidence RAG → 고정 메트릭",
        "formulae": "가중합 = Σ(metric × weight), 결측 시 가중 재분배",
        "label_policy": "Adopt/Prototype/Monitor/Archive (설계 중)",
        "device_thresholds": config.get("edge_thresholds", {}),
        "sensitivity": decision.get("weights_meta", {}),
        "risk_policy": "데이터 결측/표준 미확인 시 보수적 하향",
        "execution_meta": {
            "timestamp": exec_meta.get("ts"),
            "version": exec_meta.get("version", "v0"),
        },
    }

    write_structured_outputs(
        state.get("scores", {}),
        state.get("evidence", {}),
        api_rows=api_rows,
        decision=decision,
        summary_card=summary_card,
    )

    report_payload = {
        "decision": decision,
        "scores": state.get("scores", {}),
        "evidence": state.get("evidence", {}),
        "api_metrics": state.get("api", {}),
        "synthesis": state.get("synthesis", {}),
        "routing": state.get("routing", {}),
        "summary_card": summary_card,
        "main_body": main_body,
        "references": references,
        "appendix": appendix,
        "performance": performance_metrics,
        "metadata": {
            "patent_collection": state.get("index", {}).get("patents_index", PATENT_COLLECTION),
            "trl_collection": state.get("index", {}).get("trl_ref_index", TRL_COLLECTION),
            "timestamp": exec_meta.get("ts"),
            "source_badges": exec_meta.get("source_badges", {}),
            "max_snippets_per_metric": state.get("config", {}).get("max_snippets_per_metric", 3),
            "api_summary": state.get("api", {}).get("summary", {}),
            "embedding_meta": exec_meta.get("embedding", {}),
        },
    }
    report_payload["summary"] = decision
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
    graph.add_edge("TRL", "CLAIMS")
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
