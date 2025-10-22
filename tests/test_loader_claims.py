from chunks.pdf_loader import parse_claims_from_text


def test_claim_parsing_independent_and_dependent():
    sample = """
    CLAIMS
    1. A method comprising receiving sensor data and generating an inference model update.
    2. The method of claim 1 further comprising adapting the model according to claim 1.
    3. Claim 2. The method of claim 1 wherein the update is transmitted.
    """
    claims, _ = parse_claims_from_text(sample)
    assert len(claims) == 3
    assert claims[0]["id"] == 1
    assert claims[0]["independent"] is True
    assert claims[1]["independent"] is False
    assert claims[2]["independent"] is False
    assert "receiving sensor data" in claims[0]["text"]
