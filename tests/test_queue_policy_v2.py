"""Tests for evidence-based policy V2; historical grades remain frozen."""
import importlib.util
import json
from pathlib import Path

from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.graders import grade_labels
from sre_agent_evals.schemas import Diagnosis

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "replay_queue_policy_v2.py"
spec = importlib.util.spec_from_file_location("replay_queue_policy_v2", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_v2_applies_to_all_identical_queue_conditions_not_just_failed_ids():
    tickets = load_tickets()
    ids = {t.id for t in tickets if module.is_healthy_pool_saturation(t)}
    assert ids == {"T001", "T010", "T011", "T020", "T021",
                   "T030", "T031", "T040", "T041", "T050"}
    for t in tickets:
        changed = module.version2_ticket(t)
        if t.id in ids:
            assert changed.expected["required_actions"] == ["tune_concurrency"]
        else:
            assert changed.expected == t.expected
    # The frozen V1 label remains untouched.
    orig = next(t for t in tickets if t.id == "T010")
    assert orig.expected["required_actions"] == ["tune_concurrency", "retry_with_backoff"]


def test_capacity_errors_still_require_backoff():
    t = next(t for t in load_tickets() if t.id == "T005")
    assert "retry_with_backoff" in t.expected["required_actions"]
    assert module.version2_ticket(t).expected == t.expected


def test_queue_secondary_action_changes_only_v2_label_grade():
    t = next(t for t in load_tickets() if t.id == "T010")
    answer = Diagnosis(
        diagnosis_code="queue_saturation",
        recommended_actions=["tune_concurrency"],
        evidence=["Healthy agents, all slots in use; quota remains"],
        customer_response="Reduce fanout or adjust pool concurrency.",
    )
    assert not grade_labels(t, answer)["pass"]
    assert grade_labels(module.version2_ticket(t), answer)["pass"]
    assert not grade_labels(t, answer)["pass"]


def test_replay_preserves_v1_and_reports_both_versions():
    t = next(t for t in load_tickets() if t.id == "T010")
    answer = Diagnosis(
        diagnosis_code="queue_saturation",
        recommended_actions=["tune_concurrency"],
        evidence=["Pool busy"],
        customer_response="Reduce fanout.",
    )
    from sre_agent_evals.graders import grade_tools
    calls = [
        {"name": "query_pool_status", "arguments": {"pool_id": t.pool_id}},
        {"name": "check_quota", "arguments": {"org_id": t.org_id}},
    ]
    row = {
        "ticket_id": t.id, "model": "test-model", "response": answer.model_dump(),
        "tool_calls": calls, "tool_grade": grade_tools(t, calls),
        "label_grade": grade_labels(t, answer), "judge_grade": {"pass": True},
        "solved": False, "error": None,
    }
    saved = json.dumps(row)
    rescored = module.replay([row], [t])[0]
    assert json.dumps(row) == saved
    assert rescored["v1_strict_solved"] is False
    assert rescored["v2_strict_solved"] is True
    assert module.summary([rescored])["test-model"]["changed_ticket_ids"] == ["T010"]
