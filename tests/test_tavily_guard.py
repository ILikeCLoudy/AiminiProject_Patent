import pytest

from adapters.link_finder_tavily import pick_snippets, snapshot_and_extract, search_official_links


def test_tavily_disabled_returns_empty():
    cfg = {"tavily": {"enabled": False}}
    exec_meta = {}
    links = search_official_links(cfg, exec_meta, "test query")
    assert links == []
    assert exec_meta["tavily"]["searches"][0]["num_links"] == 0


def test_tavily_whitelist_guard(tmp_path):
    cfg = {"tavily": {"enabled": True, "whitelist_domains": ["etsi.org"], "timeout_s": 1}}
    exec_meta = {}
    with pytest.raises(ValueError):
        snapshot_and_extract(cfg, exec_meta, "https://example.com/not-allowed")


def test_pick_snippets_limits():
    text = "\n\n".join(["para" + str(i) for i in range(5)])
    snippets = pick_snippets(text, max_chars=10, max_snippets=2)
    assert len(snippets) == 2
