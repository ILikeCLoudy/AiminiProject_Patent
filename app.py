"""CLI entry point for the agent pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore

if load_dotenv is not None:  # pragma: no cover - optional dependency
    load_dotenv()

from agents.master import MasterAgent


def _convert_scalar(value: str) -> Any:
    """Convert a YAML scalar string into a Python object."""
    value = value.strip()
    if not value:
        return ""
    if value[0] in {'"', "'"} and value[-1] == value[0]:
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_yaml_naive(path: Path) -> Dict[str, Any]:
    """Parse a minimal subset of YAML (key/value with simple lists)."""
    result: Dict[str, Any] = {}
    current_key: str | None = None

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="ignore")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current_key is None:
                continue
            result.setdefault(current_key, [])
            result[current_key].append(_convert_scalar(line[2:].strip()))
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                current_key = key
                result[current_key] = []
            else:
                result[key] = _convert_scalar(value)
                current_key = None
    return result


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load YAML content using PyYAML when available, otherwise fallback parser."""
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return _load_yaml_naive(path)

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)  # type: ignore[no-any-return]


def initialise_state(config: Dict[str, Any], metas: List[Dict[str, Any]], pdfs: List[str]) -> Dict[str, Any]:
    """Create the shared state dictionary populated with configuration and metadata."""
    weights_config = config.get("weights", "use_default")
    cache_ttl = config.get("cache_ttl_days", 30)
    max_snippets = config.get("max_snippets_per_metric", 3)
    k_per_query = config.get("k_per_query", 6)
    retrieval_alpha = config.get("retrieval_alpha", 0.6)

    embedding_backend = config.get("embedding_backend", "openai")
    openai_model = config.get("openai_model", "text-embedding-3-small")
    openai_timeout = config.get("openai_timeout_s", 30)
    openai_api_env = config.get("openai_api_key_env", "OPENAI_API_KEY")

    state: Dict[str, Any] = {
        "config": {
            "weights": weights_config,
            "seed": config.get("seed", 42),
            "cache_ttl_days": cache_ttl,
            "max_snippets_per_metric": max_snippets,
            "k_per_query": k_per_query,
            "retrieval_alpha": retrieval_alpha,
            "persist_dir": config.get("persist_dir", "cache/chroma"),
            "embedding_backend": embedding_backend,
            "openai_model": openai_model,
            "openai_timeout_s": openai_timeout,
            "openai_api_key_env": openai_api_env,
            # Include all other config sections for agents to access
            "api": config.get("api", {}),
            "llm": config.get("llm", {}),
            "tavily": config.get("tavily", {}),
            "keywords": config.get("keywords", []),
            "cpc": config.get("cpc", []),
            "period": config.get("period", {}),
            "edge_thresholds": config.get("edge_thresholds", {}),
            "planner_llm": config.get("planner_llm", "gpt-4o-mini"),
        },
        "inputs": {"pdfs": pdfs, "metas": metas},
        "index": {},
        "evidence": {
            "trl": {"level": None, "snippets": [], "ref_snippets": []},
            "claims": {"num_independent": None, "avg_len_tokens": None, "pattern_stats": {}, "snippets": []},
        },
        "scores": {
            "trl": None,
            "claim": None,
            "legal": None,
            "family": None,
            "foreign": None,
            "renewal": None,
            "std": None,
            "generality": None,
            "originality": None,
            "fto": 0,
        },
        "decision": {"total": None, "label": None, "flags": []},
        "exec_meta": {"source_badges": {}},
    }
    state["exec_meta"]["cache_ttl_days"] = cache_ttl
    state["exec_meta"]["weights"] = weights_config
    state["exec_meta"]["seed"] = state["config"]["seed"]

    patent_meta = next((meta for meta in metas if meta.get("doc_id") != "SWTRLs"), metas[0] if metas else {})
    scores = state["scores"]

    legal_status = patent_meta.get("legal_status")
    if legal_status is not None:
        scores["legal"] = 70.0 if legal_status.lower() == "granted" else 55.0
    family_size = patent_meta.get("family_size")
    if isinstance(family_size, int):
        scores["family"] = max(30.0, min(90.0, 40.0 + family_size * 10.0))
    scores["foreign"] = 80.0 if patent_meta.get("foreign_oriented") else 45.0
    renewal_years = patent_meta.get("renewal_years")
    if isinstance(renewal_years, int):
        scores["renewal"] = 40.0 + min(renewal_years, 5) * 5.0
    scores["std"] = 65.0 if patent_meta.get("std_participation") else 35.0
    scores["fto"] = -10.0 if patent_meta.get("sep_declared") else 0.0

    exec_meta = state["exec_meta"]
    exec_meta.setdefault("source_badges", {})
    embed_meta = exec_meta.setdefault("embedding", {})
    embed_meta.setdefault("backend", embedding_backend)
    embed_meta.setdefault("model", openai_model)
    embed_meta.setdefault("timeout_s", openai_timeout)
    exec_meta.setdefault("openai_api_key_env", openai_api_env)
    exec_meta["source_badges"].update(
        {
            "legal": "Manual",
            "family": "Manual",
            "foreign": "Manual",
            "renewal": "Manual",
            "std": "Manual",
            "generality": "Pending",
            "originality": "Pending",
        }
    )
    if scores["fto"] < 0:
        exec_meta["source_badges"]["fto"] = "Manual"
    return state


def persist_state(state: Dict[str, Any], exec_meta: Dict[str, Any]) -> None:
    """Write state artifacts to disk."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs_dir / "exec_meta.json").write_text(json.dumps(exec_meta, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run edge AI patent analysis pipeline.")
    parser.add_argument("--pdfs", nargs="+", help="List of PDF paths (patent + reference).")
    parser.add_argument("--metas", nargs="+", help="List of YAML metadata files.")
    parser.add_argument("--config", default="configs/user_config.sample.json", help="JSON configuration file (default: configs/user_config.sample.json).")
    parser.add_argument("--query", help="Natural language query for patent search and routing.")
    parser.add_argument("--topk", type=int, help="Number of top candidates to evaluate when using --query.")
    return parser.parse_args()


def main() -> None:
    """Run the end-to-end pipeline from CLI arguments."""
    args = parse_args()

    config_path = Path(args.config)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []

    # Default query mode: use catalog if no pdfs/metas specified
    if not args.pdfs and not args.metas and not args.query:
        args.query = "edge AI on-device inference"
        print(f"No arguments provided. Using default query mode: '{args.query}'")

    if args.query:
        from routing.router import select_candidates

        catalog_cfg = config.get("catalog", {})
        candidates = select_candidates(args.query, config, top_k=args.topk or catalog_cfg.get("top_k", 3))
        if not candidates:
            raise RuntimeError("No candidates matched the query.")

        reference_pdfs = [str(Path(path)) for path in catalog_cfg.get("reference_pdfs", [])]
        reference_meta_paths = [Path(path) for path in catalog_cfg.get("reference_metas", [])]

        for candidate in candidates:
            candidate_pdf = str(Path(candidate["pdf"]))
            candidate_meta_path = Path(candidate["meta"])
            pdf_paths = [candidate_pdf] + reference_pdfs
            meta_paths = [candidate_meta_path] + reference_meta_paths
            metas = [load_yaml_file(path) for path in meta_paths]

            state = initialise_state(config, metas, pdf_paths)
            state.setdefault("inputs", {})["query"] = args.query
            state["inputs"]["candidate"] = candidate

            master = MasterAgent()
            master.run(state)
            persist_state(state, state.get("exec_meta", {}))
            results.append(
                {
                    "candidate": candidate,
                    "decision": state.get("decision", {}),
                    "scores": state.get("scores", {}),
                    "report_path": state.get("decision", {}).get("report_path"),
                }
            )
    else:
        if not args.pdfs or not args.metas:
            raise ValueError("When --query is not provided, --pdfs and --metas must be supplied.")

        pdf_paths = [str(Path(path)) for path in args.pdfs]
        meta_paths = [Path(path) for path in args.metas]
        metas = [load_yaml_file(path) for path in meta_paths]

        state = initialise_state(config, metas, pdf_paths)

        master = MasterAgent()
        master.run(state)

        persist_state(state, state.get("exec_meta", {}))

        exec_meta = state.get("exec_meta", {})
        config = state.get("config", {})
        print(f"orchestrator: {exec_meta.get('orchestrator')} / embedding_backend: {config.get('embedding_backend')} ({config.get('openai_model')})")
        vector_meta = exec_meta.get("vector", {})
        print(f"vector_backend: {vector_meta.get('backend')}  persist_dir: {vector_meta.get('persist_dir')}  collection: {vector_meta.get('collection')}")
        embedding_meta = exec_meta.get("embedding", {})
        api_meta = exec_meta.get("api", {})
        print(f"API calls {api_meta.get('calls', 0)} (cached {api_meta.get('cached', 0)}, batches {api_meta.get('batches', 0)})")
        print(f"Embedding snippets {embedding_meta.get('snippets', 0)} (~{embedding_meta.get('tokens_est', 0)} tokens / cap={embedding_meta.get('cap')})")

        decision = state.get("decision", {})
        trl_snippets = len(state.get("evidence", {}).get("trl", {}).get("snippets", []))
        claim_snippets = len(state.get("evidence", {}).get("claims", {}).get("snippets", []))

        print(f"Total Score: {decision.get('total', 0):.2f}")
        print(f"Label: {decision.get('label', 'N/A')}")
        print(f"Evidence snippets - TRL: {trl_snippets}, Claims: {claim_snippets}")
        if decision.get("report_path"):
            print(f"Report generated at: {decision['report_path']}")

        ingestion_metrics = state.get("metrics", {}).get("ingestion", {})
        embedded = ingestion_metrics.get("embedded", 0)
        skipped = ingestion_metrics.get("skipped", 0)
        embedding_meta = exec_meta.get("embedding", {})
        print(f"embedded: {embedding_meta.get('embedded', 0)}, skipped: {embedding_meta.get('skipped', 0)}")

        retrieval_meta = exec_meta.get("retrieval", {})
        trl_k = retrieval_meta.get("trl_k_per_query", state["config"].get("k_per_query"))
        claim_k = retrieval_meta.get("claims_k_per_query", state["config"].get("k_per_query"))
        trl_count = retrieval_meta.get("trl_snippets", trl_snippets)
        claim_count = retrieval_meta.get("claims_snippets", claim_snippets)
        print(f"retrieved: TRL k={trl_k} (snippets={trl_count}), Claims k={claim_k} (snippets={claim_count})")
        return

    ranking = sorted(
        results,
        key=lambda item: (item["decision"].get("total") or -1),
        reverse=True,
    )
    ranking_payload = {
        "query": args.query,
        "results": ranking,
    }
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "ranking.json").write_text(json.dumps(ranking_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Evaluated {len(ranking)} candidates for query: {args.query}")
    for idx, result in enumerate(ranking, start=1):
        decision = result["decision"]
        report_path = result.get("report_path")
        print(
            f"{idx}. {result['candidate'].get('doc_id')} ??score {decision.get('total', 0):.2f} "
            f"label {decision.get('label', 'N/A')} (report: {report_path})"
        )


if __name__ == "__main__":
    main()
