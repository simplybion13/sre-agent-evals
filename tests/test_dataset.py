from sre_agent_evals.fixtures import load_tickets, lookup_fixture


def test_50_unique_tickets_and_expected_categories():
    tickets = load_tickets()
    assert len(tickets) == 50
    assert len({t.id for t in tickets}) == 50
    assert len({t.category for t in tickets}) >= 8
    for ticket in tickets:
        assert ticket.expected["required_actions"]
        assert ticket.expected["required_tools"]
        assert lookup_fixture(ticket, "pool", "different-pool") == {"error": "resource_not_found_or_access_denied"}
        assert lookup_fixture(ticket, "pool", ticket.pool_id)["pool_id"] == ticket.pool_id


def test_data_generation_is_deterministic(tmp_path):
    from pathlib import Path
    content = (Path(__file__).resolve().parents[1] / "data" / "tickets.jsonl").read_bytes()
    assert content.startswith(b'{"id": "T001"')