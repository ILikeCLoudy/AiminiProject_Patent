import pytest

from agents.master import MasterAgent
from orchestrator.langgraph_runner import build_langgraph, UnsupportedOrchestrator


def test_orchestrator_config_flag():
    exec_meta = {}
    try:
        workflow = build_langgraph(exec_meta)
    except UnsupportedOrchestrator:
        pytest.skip("langgraph not installed")
    assert exec_meta.get("orchestrator") == "langgraph"
    assert hasattr(workflow, "invoke")


def test_master_plan_includes_join():
    plan = MasterAgent().plan({})
    assert plan[0] == "INGEST"
    assert "JOIN" in plan
