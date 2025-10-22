"""Tavily-powered official link finder and snapshot utilities."""
from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any, Dict, List
from urllib.parse import urlparse

try:
    import html2text
except ImportError:  # pragma: no cover - optional dependency
    html2text = None  # type: ignore

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # noqa: F401  # reserved for future parsing
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None  # type: ignore


try:  # pragma: no cover - optional dependency
    from tavily import TavilyClient
except ImportError:  # pragma: no cover - optional dependency
    TavilyClient = None  # type: ignore

SAFE_HEADERS = {"User-Agent": "EdgeAI-PatentAgent/0.3"}


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _is_whitelisted(url: str, whitelist: List[str]) -> bool:
    domain = _domain(url)
    return any(domain.endswith(item.lower()) for item in whitelist)


def _tavily_client(api_key: str | None) -> Any:
    if TavilyClient is None:
        raise RuntimeError("tavily-python package not installed.")
    if not api_key:
        raise RuntimeError("Tavily API key not provided.")
    return TavilyClient(api_key=api_key)


def search_official_links(cfg: Dict[str, Any], exec_meta: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    """Search official sources using Tavily (if enabled)."""
    tv_cfg = cfg.get("tavily", {})
    if not tv_cfg.get("enabled", False):
        exec_meta.setdefault("tavily", {}).setdefault("searches", []).append({"query": query, "num_links": 0})
        return []

    api_key_env = tv_cfg.get("api_key_env", "TAVILY_API_KEY")
    api_key = os.environ.get(api_key_env)
    try:
        client = _tavily_client(api_key)
    except RuntimeError as err:
        exec_meta.setdefault("warnings", []).append(str(err))
        return []

    whitelist = tv_cfg.get("whitelist_domains", [])
    max_results = int(tv_cfg.get("max_queries_per_run", 5))
    timeout = int(tv_cfg.get("timeout_s", 20))

    try:
        response = client.search(query=query, max_results=max_results, timeout=timeout)
    except Exception as exc:  # pragma: no cover - network error
        exec_meta.setdefault("warnings", []).append(f"Tavily search failed: {exc}")
        return []

    links: List[Dict[str, Any]] = []
    for item in response.get("results", []):
        url = item.get("url")
        if not url or not _is_whitelisted(url, whitelist):
            continue
        links.append({"url": url, "title": item.get("title")})

    exec_meta.setdefault("tavily", {}).setdefault("searches", []).append(
        {"query": query, "num_links": len(links), "whitelist": whitelist}
    )
    return links


def snapshot_and_extract(cfg: Dict[str, Any], exec_meta: Dict[str, Any], url: str) -> Dict[str, Any]:
    """Download and snapshot whitelisted content, returning metadata."""
    tv_cfg = cfg.get("tavily", {})
    whitelist = tv_cfg.get("whitelist_domains", [])
    if not _is_whitelisted(url, whitelist):
        raise ValueError(f"non-whitelisted domain: {url}")

    snapshot_dir = tv_cfg.get("snapshot_dir", "data/snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    if requests is None:
        raise RuntimeError("requests package not installed")
    timeout = int(tv_cfg.get("timeout_s", 20))
    response = requests.get(url, headers=SAFE_HEADERS, timeout=timeout)
    response.raise_for_status()

    html = response.text
    if html2text is None:
        raise RuntimeError("html2text package not installed")
    parser = html2text.HTML2Text()
    parser.ignore_links = False
    text = parser.handle(html)

    checksum = _sha256_text(text)
    basename = _domain(url).replace(".", "_")
    identifier = checksum.split(":")[1][:12]

    html_path = os.path.join(snapshot_dir, f"{basename}_{identifier}.html")
    txt_path = os.path.join(snapshot_dir, f"{basename}_{identifier}.txt")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write(text)

    meta = {
        "url": url,
        "html_path": html_path,
        "txt_path": txt_path,
        "text_checksum": checksum,
        "retrieved_at": time.time(),
    }
    exec_meta.setdefault("tavily", {}).setdefault("snapshots", []).append(meta)
    return {
        "doc_ref": txt_path,
        "text_checksum": checksum,
        "url": url,
        "source": _domain(url),
    }


def pick_snippets(text: str, max_chars: int = 900, max_snippets: int = 3, cue: str = "") -> List[str]:
    """Return ranked snippets from snapshot text respecting size limits."""
    paragraphs = [para.strip() for para in text.split("\n\n") if para.strip()]
    scored: List[tuple[float, str]] = []
    for para in paragraphs:
        score = (1.0 if cue and cue.lower() in para.lower() else 0.0) + min(len(para), max_chars) / max_chars
        scored.append((score, para[:max_chars]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [para for _, para in scored[: max_snippets or 0]]


__all__ = ["search_official_links", "snapshot_and_extract", "pick_snippets"]
