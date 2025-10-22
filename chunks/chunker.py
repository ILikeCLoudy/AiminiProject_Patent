"""Chunk creation logic for embeddings."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _window_text(text: str, min_len: int, max_len: int, overlap: int) -> List[str]:
    """Return sliding window slices of ``text`` according to size constraints."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    if len(cleaned) <= max_len:
        return [cleaned]

    chunk_size = max(min_len, min(max_len, len(cleaned)))
    windows: List[str] = []
    start = 0
    end_limit = len(cleaned)

    while start < end_limit:
        end = min(end_limit, start + chunk_size)
        chunk = cleaned[start:end].strip()
        if chunk:
            windows.append(chunk)
        if end == end_limit:
            break
        start = max(0, end - overlap)
    return windows


def _normalize_name(doc_id: Optional[str], name: str) -> str:
    """Return a section name string enriched with doc identifier for uniqueness."""
    prefix = (doc_id or "doc").replace(" ", "_")
    clean_name = name.strip().replace(" ", "_") or "section"
    return f"{prefix}-{clean_name}"


def _make_section_chunks(name: str, text: str, min_len: int, max_len: int, overlap: int) -> List[Dict[str, Any]]:
    """Create chunk payloads for abstract or other sections."""
    section_name = name.strip() or "section"
    chunks: List[Dict[str, Any]] = []
    for idx, piece in enumerate(_window_text(text, min_len, max_len, overlap)):
        chunks.append(
            {
                "chunk_id": f"sec:{section_name}:{idx}",
                "text": piece,
                "meta": {"section": section_name, "len_chars": len(piece)},
            }
        )
    return chunks


def _flush_dependent_claims(
    buffer_texts: List[str],
    buffer_ids: List[Any],
    overlap: int,
    doc_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Convert buffered dependent claims into chunk records."""
    if not buffer_texts:
        return []

    combined = " ".join(buffer_texts).strip()
    if not combined:
        return []

    primary_id = _normalize_name(doc_id, str(buffer_ids[0]))
    id_meta: Any = buffer_ids[0] if len(buffer_ids) == 1 else buffer_ids[:]
    chunks: List[Dict[str, Any]] = []
    for idx, piece in enumerate(_window_text(combined, 500, 800, overlap)):
        chunks.append(
            {
                "chunk_id": f"claim:{primary_id}:{idx}",
                "text": piece,
                "meta": {
                    "section": "claims",
                    "claim_id": id_meta,
                    "independent": False,
                    "doc_id": doc_id,
                    "source_type": "PDF",
                    "source": "LocalPDF",
                    "source_id": doc_id,
                    "doc_ref": None,
                    "len_chars": len(piece),
                },
            }
        )
    return chunks


def chunk_for_embedding(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create embedding-ready chunks from structured document data."""
    chunks: List[Dict[str, Any]] = []
    doc_id = document.get("doc_id")

    abstract = document.get("abstract")
    if abstract:
        section_name = _normalize_name(doc_id, "abstract")
        chunks.extend(
            {
                **chunk,
                "chunk_id": f"sec:{section_name}:{chunk['chunk_id'].split(':')[-1]}",
                "meta": {**chunk["meta"], "section": "abstract", "doc_id": doc_id, "source_type": "PDF", "source": "LocalPDF", "source_id": doc_id, "doc_ref": None},
            }
            for chunk in _make_section_chunks(section_name, abstract, 400, 800, 60)
        )

    for section in document.get("sections") or []:
        name = section.get("name", "section")
        text = section.get("text", "")
        normalized_name = _normalize_name(doc_id, name)
        chunks.extend(
            {
                **chunk,
                "chunk_id": f"sec:{normalized_name}:{chunk['chunk_id'].split(':')[-1]}",
                "meta": {**chunk["meta"], "section": name, "doc_id": doc_id, "source_type": "PDF", "source": "LocalPDF", "source_id": doc_id, "doc_ref": None},
            }
            for chunk in _make_section_chunks(normalized_name, text, 400, 800, 60)
        )

    dependent_texts: List[str] = []
    dependent_ids: List[Any] = []
    dependent_char_count = 0

    def flush_dependents() -> None:
        nonlocal dependent_texts, dependent_ids, dependent_char_count, chunks
        if not dependent_texts:
            return
        chunks.extend(_flush_dependent_claims(dependent_texts, dependent_ids, 60, doc_id))
        dependent_texts = []
        dependent_ids = []
        dependent_char_count = 0

    for claim in document.get("claims") or []:
        claim_text = (claim.get("text") or "").strip()
        claim_id = claim.get("id")
        is_independent = bool(claim.get("independent"))

        if is_independent:
            flush_dependents()
            for idx, piece in enumerate(_window_text(claim_text, 300, 800, 60)):
                chunks.append(
                    {
                        "chunk_id": f"claim:{_normalize_name(doc_id, str(claim_id))}:{idx}",
                        "text": piece,
                        "meta": {
                            "section": "claims",
                            "claim_id": claim_id,
                            "independent": True,
                            "doc_id": doc_id,
                            "source_type": "PDF",
                            "source": "LocalPDF",
                            "source_id": doc_id,
                            "doc_ref": None,
                            "len_chars": len(piece),
                        },
                    }
                )
        else:
            if claim_text:
                dependent_texts.append(claim_text)
                dependent_ids.append(claim_id)
                dependent_char_count += len(claim_text)
                if dependent_char_count >= 700:
                    flush_dependents()

    flush_dependents()
    return chunks
