"""Offline judge-only replay selectors never alter candidate records."""
from scripts.rejudge_runs import select_rows
from sre_agent_evals.fixtures import load_tickets


def test_select_saved_rows_preserves_original_judge_and_strict_scores():
    ticket = next(t for t in load_tickets() if t.category == "image")
    record = {
        "ticket_id": ticket.id, "model": "gpt-4.1", "solved": False,
        "judge_grade": {"pass": False},
        "response": {"diagnosis_code": "image_mismatch",
                     "recommended_actions": ["select_supported_image"],
                     "evidence": ["ImageNotFound"], "customer_response": "Use ubuntu-22.04."},
        "tool_calls": [{"name": "lookup_docs", "arguments": {"topic": "images"}}],
    }
    chosen = select_rows([record], load_tickets(), ticket.id, "gpt-4.1")
    assert chosen == [(record, ticket)]
    assert record["solved"] is False
    assert record["judge_grade"] == {"pass": False}
    assert select_rows([record], load_tickets(), "nonexistent", "gpt-4.1") == []
    assert select_rows([record], load_tickets(), ticket.id, "gpt-4.1-mini") == []
