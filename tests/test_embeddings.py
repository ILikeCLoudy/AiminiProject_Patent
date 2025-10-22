import os

from embeddings.factory import DummyEmbedder, get_embedder


def test_openai_fallback(monkeypatch):
    cfg = {"embedding_backend": "openai", "openai_model": "text-embedding-3-small"}
    exec_meta = {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    embedder, meta = get_embedder(cfg, exec_meta)
    assert isinstance(embedder, DummyEmbedder)
    assert exec_meta["warnings"]
    assert meta["backend"] == "openai"


def test_dummy_embedding_deterministic():
    dummy = DummyEmbedder()
    text = ["hello", "hello"]
    vecs = dummy.embed(text)
    assert vecs[0] == vecs[1]
