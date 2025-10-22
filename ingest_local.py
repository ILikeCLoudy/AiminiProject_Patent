"""Local ingestion pipeline for patent PDFs with fingerprint caching."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from chunks.chunker import chunk_for_embedding
from chunks.indexer import upsert_chunks
from chunks.pdf_loader import load_pdf

PATENT_COLLECTION = "patents"
TRL_COLLECTION = "trl_ref"


def _determine_collection(doc_id: str) -> str:
    """Return the target collection name for the given document identifier."""
    normalized = doc_id.lower()
    if "swtrl" in normalized or normalized.startswith("swtrl"):
        return TRL_COLLECTION
    return PATENT_COLLECTION


def _check_fingerprint(state: Dict[str, Any], doc_id: str, metadata: Dict[str, Any]) -> bool:
    """Check whether the document fingerprint matches cache; update cache if changed."""
    exec_meta = state.setdefault("exec_meta", {})
    fingerprints = exec_meta.setdefault("fingerprints", {})
    fingerprint = metadata["fingerprint"]
    cached = fingerprints.get(doc_id)
    if cached and cached.get("fingerprint") == fingerprint:
        return True
    fingerprints[doc_id] = {
        "fingerprint": fingerprint,
        "parser": metadata.get("parser"),
        "pages": metadata.get("pages"),
        "claims": metadata.get("claims"),
    }
    return False


def ingest_pdfs(state: Dict[str, Any], pdf_paths: List[str]) -> Dict[str, Any]:
    """Ingest the provided PDFs into lightweight in-memory indices."""
    summary: Dict[str, Any] = {"documents": [], "counts": {}, "embedded": 0, "skipped": 0}
    exec_meta = state.setdefault("exec_meta", {})
    logs = exec_meta.setdefault("logs", [])
    config = state.get("config", {})

    for pdf_path in pdf_paths:
        document, metadata = load_pdf(pdf_path)
        doc_id = document.get("doc_id") or Path(pdf_path).stem
        logs.append(metadata.get("log", f"{doc_id}: extraction completed"))

        if _check_fingerprint(state, doc_id, metadata):
            summary["documents"].append(
                {"doc_id": doc_id, "collection": None, "count": 0, "skipped": "fingerprint"}
            )
            summary["counts"][doc_id] = 0
            summary["skipped"] += 1
            logs.append(f"{doc_id}: fingerprint unchanged, skipping embedding.")
            continue

        collection = _determine_collection(doc_id)
        chunks = chunk_for_embedding(document)
        for chunk in chunks:
            chunk["meta"].setdefault("doc_id", doc_id)
            chunk["meta"]["source_path"] = str(pdf_path)
            chunk["meta"]["fingerprint"] = metadata["fingerprint"]
            chunk["meta"]["doc_ref"] = str(pdf_path)

        result = upsert_chunks(chunks, collection, config=config, exec_meta=exec_meta)
        summary["documents"].append(
            {
                "doc_id": doc_id,
                "collection": collection,
                "count": result["count"],
                "skipped": result.get("skipped", 0),
            }
        )
        summary["counts"][doc_id] = result["count"]
        summary["embedded"] += result["count"]
        summary["skipped"] += result.get("skipped", 0)

    return summary


def run_ingestion(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute ingestion based on the pipeline state definition."""
    pdf_paths = state.get("inputs", {}).get("pdfs", [])
    if not pdf_paths:
        return {"ok": False, "logs": ["No PDFs provided for ingestion."], "updates": {}}

    ingest_result = ingest_pdfs(state, pdf_paths)
    state.setdefault("index", {})
    state["index"]["patents_index"] = PATENT_COLLECTION
    state["index"]["trl_ref_index"] = TRL_COLLECTION

    exec_meta = state.setdefault("exec_meta", {})
    logs = exec_meta.setdefault("logs", [])
    logs.append(
        f"Ingestion completed: embedded={ingest_result['embedded']}, skipped={ingest_result['skipped']}"
    )
    exec_meta.setdefault("ingestion", {})["last_result"] = ingest_result

    update_payload = {
        "ok": True,
        "updates": {
            ("index", "patents_index"): PATENT_COLLECTION,
            ("index", "trl_ref_index"): TRL_COLLECTION,
        },
        "summary": ingest_result,
    }
    return update_payload


__all__ = ["ingest_pdfs", "run_ingestion", "PATENT_COLLECTION", "TRL_COLLECTION"]
