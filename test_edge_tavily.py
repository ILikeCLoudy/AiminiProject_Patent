"""Test script for edge performance extraction with Tavily."""
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from retrieval.edge_metrics import extract_edge_performance
from app import load_yaml_file

def test_edge_extraction():
    """Test edge performance extraction with Tavily."""
    # Load configuration
    config_path = Path("configs/user_config.sample.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Load patent_C metadata
    meta_path = Path("meta/patent_C.yaml")
    meta = load_yaml_file(meta_path)

    # Create minimal state
    state = {
        "config": config,
        "inputs": {
            "metas": [meta]
        },
        "evidence": {},
        "exec_meta": {}
    }

    print("=" * 80)
    print("Testing Edge Performance Extraction with Tavily")
    print("=" * 80)
    print(f"\nPatent: {meta.get('doc_id')} - {meta.get('title')}")
    print(f"Tavily enabled: {config.get('tavily', {}).get('enabled', False)}")
    print(f"Edge adapter use_tavily: {config.get('edge_adapter', {}).get('use_tavily', False)}")

    # Check API keys
    tavily_key = os.environ.get("TAVILY_API_KEY")
    print(f"\nTAVILY_API_KEY: {'[OK] SET' if tavily_key else '[X] NOT SET'}")

    if not tavily_key:
        print("\n[WARNING] TAVILY_API_KEY not set. Tavily search will be skipped.")
        print("   To test with Tavily, set your API key in .env file:")
        print("   TAVILY_API_KEY=your_api_key_here")

    print("\n" + "-" * 80)
    print("Starting extraction...")
    print("-" * 80)

    # Extract performance metrics
    metrics = extract_edge_performance(state)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    if metrics:
        print(f"\n[OK] Extracted {len(metrics)} metrics:")
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

    # Show warnings
    warnings = state.get("exec_meta", {}).get("warnings", [])
    if warnings:
        print("\n" + "-" * 80)
        print("WARNINGS:")
        print("-" * 80)
        for warning in warnings:
            print(f"  [!] {warning}")

    # Show Tavily search metadata
    tavily_meta = state.get("exec_meta", {}).get("tavily", {})
    if tavily_meta:
        print("\n" + "-" * 80)
        print("TAVILY METADATA:")
        print("-" * 80)
        searches = tavily_meta.get("searches", [])
        for search in searches:
            query = search.get("query", "")
            num_links = search.get("num_links", 0)
            print(f"  Query: {query[:60]}...")
            print(f"  Links found: {num_links}")

        snapshots = tavily_meta.get("snapshots", [])
        if snapshots:
            print(f"\n  Snapshots saved: {len(snapshots)}")
            for snap in snapshots:
                print(f"    - {snap.get('url')}")
                print(f"      -> {snap.get('txt_path')}")

    print("\n" + "=" * 80)
    return metrics

if __name__ == "__main__":
    test_edge_extraction()
