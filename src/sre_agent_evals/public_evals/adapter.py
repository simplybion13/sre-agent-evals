"""Minimal, offline adapter for a normalized ITBench-derived scenario.

This is NOT a parser for the upstream ITBench-AA native dataset format.
That mapping requires dataset inspection and version pinning in M2.2.
"""

from __future__ import annotations

from typing import Any


def adapt_normalized_scenario(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a validated intermediate record into candidate input and grader-only labels.

    Returns (agent_input, grader_reference). Neither result aliases the source.
    No network access, model calls, or side effects.
    """
    if not isinstance(record, dict):
        raise ValueError("scenario must be an object")
    scenario_id = record.get("scenario_id")
    incident = record.get("incident")
    evidence = record.get("evidence")
    ground_truth = record.get("ground_truth")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id must be a nonempty string")
    if not isinstance(incident, dict) or not isinstance(incident.get("summary"), str) or not incident["summary"].strip():
        raise ValueError("incident.summary must be a nonempty string")
    if not isinstance(evidence, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("source"), str)
        and isinstance(item.get("content"), str)
        for item in evidence
    ):
        raise ValueError("evidence must be a list of source/content objects")
    if not isinstance(ground_truth, dict):
        raise ValueError("ground_truth must be an object")
    entities = ground_truth.get("root_cause_entities")
    if not isinstance(entities, list) or not entities or not all(
        isinstance(entity, str) and entity.strip() for entity in entities
    ):
        raise ValueError("root_cause_entities must be a nonempty list of strings")
    # Explicit allowlist: never forward arbitrary upstream keys or labels.
    agent_input = {
        "scenario_id": scenario_id,
        "incident": {"summary": incident["summary"], "observations": list(incident.get("observations", []))},
        "evidence": [{"source": item["source"], "content": item["content"]} for item in evidence],
    }
    grader_reference = {
        "scenario_id": scenario_id,
        "root_cause_entities": list(entities),
    }
    return agent_input, grader_reference
