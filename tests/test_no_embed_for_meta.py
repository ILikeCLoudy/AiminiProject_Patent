from chunks.indexer import upsert_chunks


def test_meta_only_chunks_skipped(tmp_path):
    cfg = {
        "vector_backend": "chroma",
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "patents",
    }
    exec_meta = {}
    chunks = [
        {
            "chunk_id": "meta:001",
            "text": "metadata only payload",
            "meta": {"meta_only": True},
        },
        {
            "chunk_id": "embeddable:002",
            "text": "deployed system in production environment",
            "meta": {"section": "claims"},
        },
    ]
    result = upsert_chunks(chunks, cfg["collection_name"], config=cfg, exec_meta=exec_meta)
    assert result["count"] == 1
    assert exec_meta["embedding"]["meta_skipped"] == 1
