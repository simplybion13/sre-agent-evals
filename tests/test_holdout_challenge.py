"""Versioned synthetic challenge set: structural checks without live API calls."""
from pathlib import Path

from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.graders import grade_tools
from sre_agent_evals.judge import judge_payload
from sre_agent_evals.orchestration import collect_evidence
from sre_agent_evals.schemas import Diagnosis


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "data" / "holdout_challenge_v1.jsonl"


def test_challenge_set_has_distinct_ids_and_expected_labels():
    challenge = load_tickets(CHALLENGE)
    original = load_tickets()
    assert len(challenge) == 15
    assert len({t.id for t in challenge}) == 15
    assert not ({t.id for t in challenge} & {t.id for t in original})
    assert len({t.category for t in challenge}) >= 8
    assert all(t.expected["required_actions"] and t.expected["required_tools"] for t in challenge)


def test_controller_observed_tools_cover_challenge_labels_offline():
    for ticket in load_tickets(CHALLENGE):
        bundle = collect_evidence(ticket)
        grade = grade_tools(ticket, bundle.calls)
        assert grade["pass"], f"{ticket.id}: {grade['violations']}"


def test_rubric_v2_receives_only_retrieved_docs_not_hidden_all_docs():
    ticket = next(x for x in load_tickets() if x.category == "sku")
    answer = Diagnosis(
        diagnosis_code="sku_unsupported",
        recommended_actions=["select_supported_sku"],
        evidence=["InvalidSku"],
        customer_response="Use standard-2 or standard-4.",
    )
    baseline = judge_payload(ticket, answer, [], rubric_version=1)
    assert "retrieved_documentation" not in baseline
    assert isinstance(baseline["answer"], str)
    no_docs = judge_payload(ticket, answer, [], rubric_version=2)
    assert no_docs["retrieved_documentation"] == []
    with_docs = judge_payload(
        ticket, answer, [{"name": "lookup_docs", "arguments": {"topic": "skus"}}],
        rubric_version=2,
    )
    assert len(with_docs["retrieved_documentation"]) == 1
    assert "standard-2" in with_docs["retrieved_documentation"][0]["content"]
    assert "images" not in str(with_docs["retrieved_documentation"])


def test_holdout_missing_ids_are_not_invented():
    missing = [t for t in load_tickets(CHALLENGE) if t.job_id is None]
    assert len(missing) == 2
    for ticket in missing:
        assert [call["name"] for call in collect_evidence(ticket).calls] == ["query_pool_status"]
