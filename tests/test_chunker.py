from chunks.chunker import chunk_for_embedding


def test_claim_chunking_minimal():
    doc = {"claims": [
        {"id": 1, "text": "A device comprising ...", "independent": True},
        {"id": 2, "text": "The device wherein ...", "independent": False}
    ], "abstract": "on-device prototype test", "sections": []}
    chunks = chunk_for_embedding(doc)
    ids = [c["meta"].get("claim_id") for c in chunks if "claim_id" in c["meta"]]
    assert 1 in ids
    assert any("abstract" == c["meta"].get("section") for c in chunks)
