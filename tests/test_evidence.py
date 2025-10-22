import pytest

from retrieval.evidence_rag import _score_trl_snippet, _summarize_claim_patterns, CLAIM_CUES


def test_trl_rule_mapping():
    snippet = "The system was deployed in a production operational environment with real-time telemetry."
    assert _score_trl_snippet(snippet) == pytest.approx(8.5, rel=0.05)
    assert _score_trl_snippet("Prototype validation in lab") == pytest.approx(5.5, rel=0.05)


def test_claim_pattern_summary():
    records = [
        {"text": "A device comprising at least one sensor configured to operate.", "meta": {"section": "claims"}},
        {"text": "The device wherein the controller is configured to adapt.", "meta": {"section": "claims"}},
    ]
    stats = _summarize_claim_patterns(records)
    for cue in CLAIM_CUES:
        assert cue in stats
    assert stats["comprising"] == 1
    assert stats["wherein"] == 1
