import os
import uuid

from retrieval.vectorstore_factory import get_vectorstore


def test_vector_backend_is_chroma(tmp_path):
    cfg = {"vector_backend": "chroma", "persist_dir": str(tmp_path / "chroma"), "collection_name": "patents"}
    exec_meta = {}
    coll, path = get_vectorstore(cfg, exec_meta)
    assert exec_meta["vector"]["backend"] == "chroma"
    assert os.path.isdir(path)
    assert hasattr(coll, "add")


def test_chroma_roundtrip(tmp_path):
    cfg = {"vector_backend": "chroma", "persist_dir": str(tmp_path / "chroma"), "collection_name": "patents"}
    exec_meta = {}
    coll, _ = get_vectorstore(cfg, exec_meta)
    ids = [str(uuid.uuid4())]
    docs = ["hello chroma"]
    metas = [{"k": "v"}]
    embs = [[0.01] * 384]
    coll.add(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    coll2, _ = get_vectorstore(cfg, exec_meta)
    fetched = coll2.get(ids=ids)
    assert fetched
    assert fetched["documents"][0] == "hello chroma"
