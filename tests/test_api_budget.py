from ingestion.expand_with_api import expand_with_api


def _make_state(tmp_path, max_calls=1):
    config = {
        "api": {
            "enabled": True,
            "max_calls_per_run": max_calls,
            "batch_size": 5,
            "cache_dir": str(tmp_path / "api_cache"),
            "whitelist_domains": ["uspto.gov"],
        },
        "cache_ttl_days": 30,
    }
    meta = {
        "doc_id": "WO12345",
        "family_size": 2,
        "forward_citations_5y": 1,
        "countries": ["US"],
        "legal_status": "granted",
        "renewal_years": 2,
        "foreign_oriented": True,
        "sep_declared": False,
        "std_participation": True,
        "api_domains": ["uspto.gov"],
    }
    return {
        "config": config,
        "inputs": {"metas": [meta]},
        "exec_meta": {"ts": "2025-01-01T00:00:00"},
    }


def test_api_budget_guard(tmp_path):
    state = _make_state(tmp_path, max_calls=1)

    first = expand_with_api(state)
    assert first["ok"]
    assert state["exec_meta"]["api"]["calls"] == 1

    second = expand_with_api(state)
    assert not second["ok"]
    assert second["warnings"]
    assert state["exec_meta"]["api"]["calls"] == 1  # budget capped


def test_api_cache_hit_resets_calls(tmp_path):
    state = _make_state(tmp_path, max_calls=5)
    first = expand_with_api(state)
    assert first["ok"]
    state["exec_meta"]["api"]["calls"] = 0  # simulate new run with cached artifact
    cached = expand_with_api(state)
    assert cached["ok"]
    assert state["api"]["summary"]["cached"] >= 1
