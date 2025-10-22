from chunks.indexer import upsert_chunks
from retrieval.evidence_rag import gather_trl_evidence


def test_snippet_policy_max_chars(tmp_path):
    cfg = {
        "vector_backend": "chroma",
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "patents",
        "retrieval_alpha": 0.6,
        "k_per_query": 3,
        "max_snippets_per_metric": 2,
        "max_snippet_chars": 40,
    }
    long_text = "Deployed prototype in operational production environment with continuous real-time telemetry " * 3
    chunks = [
        {
            "chunk_id": "claims:long",
            "text": long_text,
            "meta": {"section": "claims", "doc_id": "WO2"},
        }
    ]
    upsert_chunks(chunks, cfg["collection_name"], config=cfg, exec_meta={})

    state = {
        "config": cfg,
        "index": {"patents_index": "patents", "trl_ref_index": ""},
        "exec_meta": {"ts": "2025-01-01T00:00:00"},
    }
    gather_trl_evidence(state)

    snippets = state["evidence"]["trl"]["snippets"]
    assert snippets
    assert all(len(snippet["text"]) <= cfg["max_snippet_chars"] for snippet in snippets)
