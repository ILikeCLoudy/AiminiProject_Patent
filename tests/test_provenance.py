from chunks.indexer import upsert_chunks
from ingestion.expand_with_api import expand_with_api
from retrieval.evidence_rag import gather_claims_evidence, gather_trl_evidence


def test_provenance_entries_record_checksums(tmp_path):
    cfg = {
        "vector_backend": "chroma",
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "patents",
        "retrieval_alpha": 0.6,
        "k_per_query": 3,
        "max_snippets_per_metric": 2,
        "max_snippet_chars": 80,
    }
    exec_meta = {}
    chunks = [
        {
            "chunk_id": "claims:001",
            "text": "The system is deployed in a production environment with pilot field tests and comprising adaptive modules wherein controllers coordinate field deployments.",
            "meta": {"section": "claims", "doc_id": "WO1"},
        }
    ]
    upsert_chunks(chunks, cfg["collection_name"], config=cfg, exec_meta=exec_meta)

    state = {
        "config": cfg,
        "index": {"patents_index": "patents", "trl_ref_index": ""},
        "exec_meta": {"ts": "2025-01-01T00:00:00"},
    }

    gather_trl_evidence(state)
    gather_claims_evidence(state)

    provenance = state.get("provenance", {}).get("evidence", [])
    metrics = {entry["metric"] for entry in provenance}
    assert {"trl", "claims"} <= metrics
    assert any(entry["metric"] == "trl" and entry["checksums"] for entry in provenance)
    assert any(entry["metric"] == "claims" and entry["checksums"] for entry in provenance)


def test_api_provenance_blocked_domain(tmp_path):
    state = {
        "config": {
            "api": {
                "enabled": True,
                "max_calls_per_run": 1,
                "batch_size": 5,
                "cache_dir": str(tmp_path / "api_cache"),
                "whitelist_domains": ["uspto.gov"],  # exclude other canonical domains
            },
            "cache_ttl_days": 30,
        },
        "inputs": {
            "metas": [
                {
                    "doc_id": "WO2018097365A1",
                    "publication_date": "2018-05-31",
                    "family_size": 1,
                    "forward_citations_5y": 0,
                    "countries": ["US"],
                    "legal_status": "granted",
                    "renewal_years": 1,
                    "api_domains": ["wipo.int"],
                }
            ]
        },
        "exec_meta": {"ts": "2025-01-01T00:00:00"},
    }

    expand_with_api(state)
    rows = state["api_meta"]
    assert any(row["status"] == "blocked_domain" for row in rows)
    provenance_entries = state["provenance"]["api_metrics"]
    assert provenance_entries
    latest = provenance_entries[-1]
    assert "missing_keys" in latest
