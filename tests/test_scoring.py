from scoring.scoring import weighted_total, decide_label


def test_weighted_total_with_missing():
    parts = {"trl": 80, "claim": 70, "legal": None, "family": 90, "foreign": None, "renewal": 60, "std": 40, "fto": -5}
    w = {"trl": 0.20, "claim": 0.20, "legal": 0.08, "family": 0.10, "foreign": 0.08, "renewal": 0.06, "std": 0.04, "fto": 0.02}
    total = weighted_total(parts, w)
    assert 0 <= total <= 100


def test_label_rules_and_fto():
    assert decide_label(82, flags=[]) == "A"
    lbl = decide_label(72, flags=["FTO_risk"])
    assert lbl in ("P", "M")  # 1단계 하향
