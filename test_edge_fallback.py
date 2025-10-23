"""Test edge performance extraction fallback (Priority 3: evidence snippets)."""
from retrieval.edge_metrics import extract_edge_performance

def test_fallback():
    """Test extraction from evidence snippets when Tavily is unavailable."""

    # Create state with mock evidence snippets containing performance data
    state = {
        "config": {
            "tavily": {"enabled": False},  # Disable Tavily for this test
            "edge_adapter": {"use_tavily": False}
        },
        "inputs": {
            "metas": [{
                "doc_id": "US20230012345",
                "title": "Edge AI Accelerator for Wearables"
            }]
        },
        "evidence": {
            "trl": {
                "snippets": [
                    {
                        "text": "Our edge AI accelerator achieves 35ms latency on inference tasks, "
                                "consuming only 450mW of power during operation."
                    }
                ]
            },
            "claims": {
                "snippets": [
                    {
                        "text": "The wearable device utilizes 128MB of memory for model storage, "
                                "with an accuracy delta of -1.2% compared to cloud-based inference."
                    }
                ]
            }
        },
        "exec_meta": {}
    }

    print("=" * 80)
    print("Testing Edge Performance Extraction - Fallback Mode (Priority 3)")
    print("=" * 80)
    print("\nTavily: DISABLED (testing fallback)")
    print("Evidence snippets: PROVIDED (mock data with metrics)")

    print("\n" + "-" * 80)
    print("Starting extraction...")
    print("-" * 80)

    metrics = extract_edge_performance(state)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    if metrics:
        print(f"\n[OK] Extracted {len(metrics)} metrics from evidence snippets:")
        for key, data in metrics.items():
            value = data.get("value")
            unit = data.get("unit")
            source = data.get("source")
            priority = data.get("priority")
            print(f"  - {key}: {value} {unit}")
            print(f"    Source: {source} (Priority {priority})")
    else:
        print("\n[X] No metrics extracted")

    # Show logs
    logs = state.get("exec_meta", {}).get("logs", [])
    if logs:
        print("\n" + "-" * 80)
        print("LOGS:")
        print("-" * 80)
        for log in logs:
            print(f"  {log}")

    print("\n" + "=" * 80)
    print("\nExpected: 4 metrics (latency_ms, power_mw, memory_mb, accuracy_delta)")
    print(f"Actual: {len(metrics)} metrics")
    print(f"Test: {'PASS' if len(metrics) == 4 else 'FAIL'}")
    print("=" * 80)

if __name__ == "__main__":
    test_fallback()
