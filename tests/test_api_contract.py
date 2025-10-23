from adapters.api_clients import METRIC_KEYS
from ingestion.expand_with_api import expand_with_api
from scoring.scoring import WEIGHTS, weighted_total


def _state_for_contract(tmp_path, *, whitelist=None):
    whitelist = whitelist or [
        "wipo.int",
        "uspto.gov",
        "etsi.org",
        "justice.gov",
        "nber.org",
        "patents.google.com",
    ]
    config = {
        "api": {
            "enabled": True,
            "max_calls_per_run": 5,
            "batch_size": 5,
            "cache_dir": str(tmp_path / "api_cache"),
            "whitelist_domains": whitelist,
        },
        "cache_ttl_days": 30,
    }
    meta = {
        "doc_id": "WO2018097365A1",
        "publication_date": "2018-05-31",
        "family_size": 3,
        "forward_citations_5y": 7,
        "countries": ["WO", "US"],
        "legal_status": "granted",
        "renewal_years": 4,
        "foreign_oriented": True,
        "sep_declared": True,
        "std_participation": True,
        "api_domains": ["wipo.int"],
    }
    return {
        "config": config,
        "inputs": {"metas": [meta]},
        "exec_meta": {"ts": "2025-01-01T00:00:00"},
    }


def test_api_contract_rows_have_required_fields(tmp_path):
    state = _state_for_contract(tmp_path)
    result = expand_with_api(state)
    assert result["ok"]
    rows = state["api_meta"]
    assert len(rows) >= len(METRIC_KEYS)

    metrics_present = {row["metric_key"] for row in rows}
    assert set(METRIC_KEYS).issubset(metrics_present)

    for row in rows:
        for key in ("metric_key", "source_url", "status", "fetch_ts", "cache_info"):
            assert key in row
        assert "chosen" in row

    citations_rows = [row for row in rows if row["metric_key"] == "CITATIONS_TOTAL"]
    assert len(citations_rows) >= 2
    assert sum(1 for row in citations_rows if row["chosen"]) == 1


def test_blocked_domain_status(tmp_path):
    whitelist = ["uspto.gov"]  # exclude canonical WIPO domain to trigger block
    state = _state_for_contract(tmp_path, whitelist=whitelist)
    expand_with_api(state)
    rows = state["api_meta"]
    blocked = [row for row in rows if row["status"] == "blocked_domain"]
    assert blocked
    for row in blocked:
        assert row["value"] is None


def test_weight_redistribution_flag():
    parts = {"trl": 80.0, "claim": None, "legal": 70.0, "fto": -10.0}
    total, details = weighted_total(parts, WEIGHTS, return_details=True)
    assert total >= 0
    assert details["redistributed"]
    assert "claim" in details["missing_keys"]
