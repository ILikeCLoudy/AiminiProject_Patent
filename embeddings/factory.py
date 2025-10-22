"""Embedding factory for OpenAI backend with deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Tuple

import hashlib
import math

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


class Embedder(Protocol):
    """Simple embedding protocol."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        ...


@dataclass
class DummyEmbedder:
    """Deterministic fallback embedder when API key or sdk is unavailable."""

    dimension: int = 384

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            data = bytearray(digest)
            while len(data) < self.dimension * 4:
                data.extend(hashlib.sha256(data).digest())
            vec: List[float] = []
            for idx in range(self.dimension):
                start = idx * 4
                chunk = data[start : start + 4]
                value = int.from_bytes(chunk, "little", signed=False)
                vec.append((value % 2000) / 1000.0 - 1.0)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


@dataclass
class OpenAIEmbedder:
    """Thin wrapper around OpenAI embeddings API."""

    client: Any
    model: str
    timeout_s: int

    def embed(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            timeout=self.timeout_s,
        )
        return [data.embedding for data in response.data]


def get_embedder(config: Dict[str, Any], exec_meta: Dict[str, Any]) -> Tuple[Embedder, Dict[str, Any]]:
    """Return embedder instance plus metadata."""
    backend = (config.get("embedding_backend") or "openai").lower()
    model = config.get("openai_model", "text-embedding-3-small")
    timeout = int(config.get("openai_timeout_s", 30))
    details: Dict[str, Any] = {"backend": backend, "model": model}

    if backend != "openai" or OpenAI is None:
        exec_meta.setdefault("warnings", []).append(
            "OPENAI backend unavailable, using deterministic dummy embeddings."
        )
        return DummyEmbedder(), details

    api_key_env = config.get("openai_api_key_env", "OPENAI_API_KEY")
    api_key = config.get("openai_api_key") or exec_meta.get("secrets", {}).get(api_key_env)
    if not api_key:
        import os

        api_key = os.environ.get(api_key_env)
    if not api_key:
        exec_meta.setdefault("warnings", []).append(
            f"Missing OpenAI API key (env {api_key_env}); using deterministic dummy embeddings."
        )
        return DummyEmbedder(), details

    client = OpenAI(api_key=api_key)  # type: ignore[operator]
    return OpenAIEmbedder(client=client, model=model, timeout_s=timeout), details


__all__ = ["get_embedder", "DummyEmbedder", "OpenAIEmbedder"]
