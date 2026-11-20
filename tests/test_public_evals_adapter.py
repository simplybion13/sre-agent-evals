"""No API key or external benchmark download required."""

import pytest

from sre_agent_evals.public_evals import adapt_normalized_scenario


def scenario():
    return {
        "scenario_id": "demo-1",
        "incident": {"summary": "Elevated 5xx", "observations": ["checkout errors"]},
        "evidence": [{"source": "logs", "content": "timeout"}],
        "ground_truth": {"root_cause_entities": ["checkout"]},
        "secret_label": "do-not-leak",
    }


def test_ground_truth_is_not_in_agent_input():
    agent, grader = adapt_normalized_scenario(scenario())
    assert "ground_truth" not in agent
    assert "root_cause_entities" not in str(agent)
    assert "secret_label" not in agent
    assert grader == {"scenario_id": "demo-1", "root_cause_entities": ["checkout"]}


def test_adapter_does_not_mutate_source():
    source = scenario()
    agent, grader = adapt_normalized_scenario(source)
    agent["evidence"][0]["content"] = "changed"
    grader["root_cause_entities"].append("extra")
    assert source["evidence"][0]["content"] == "timeout"
    assert source["ground_truth"]["root_cause_entities"] == ["checkout"]


@pytest.mark.parametrize("field,value", [
    ("scenario_id", ""),
    ("incident", {}),
    ("evidence", ["raw string"]),
    ("ground_truth", {"root_cause_entities": []}),
])
def test_invalid_scenarios_rejected(field, value):
    source = scenario()
    source[field] = value
    with pytest.raises(ValueError):
        adapt_normalized_scenario(source)
