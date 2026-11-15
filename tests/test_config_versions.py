"""Regression tests for the v1 baseline and constrained v2 documentation tool."""
from copy import deepcopy
from typing import get_args

import pytest
import yaml
from pydantic import TypeAdapter

from sre_agent_evals.contracts import validate_tool_contract
from sre_agent_evals.paths import DEFAULT_CONFIG_VERSION, config_paths
from sre_agent_evals.schemas import DocTopic


def load_contract(version: int) -> dict:
    _, path = config_paths(version)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_prompt_and_tool_contract_are_selected_as_a_pair():
    for version in (1, 2, 3):
        prompt, tools = config_paths(version)
        assert prompt.exists() and tools.exists()
        assert f"/v{version}/" in prompt.as_posix()
        assert f"/v{version}/" in tools.as_posix()
        assert validate_tool_contract(load_contract(version)) == version
    assert DEFAULT_CONFIG_VERSION == 3
    with pytest.raises(ValueError, match="Unsupported"):
        config_paths(4)


def test_v1_remains_a_free_text_baseline():
    spec = load_contract(1)
    assert "enum" not in spec["tools"]["lookup_docs"]["arguments"]["topic"]
    prompt, _ = config_paths(1)
    assert "Allowed diagnosis codes" in prompt.read_text(encoding="utf-8")


def test_v2_canonical_topics_match_runtime_schema():
    spec = load_contract(2)
    documented = spec["tools"]["lookup_docs"]["arguments"]["topic"]["enum"]
    runtime_schema = TypeAdapter(DocTopic).json_schema()
    assert set(documented) == set(get_args(DocTopic)) == set(runtime_schema["enum"])
    assert len(documented) == len(set(documented))
    assert "ubuntu-20.04" not in documented
    with pytest.raises(Exception):
        TypeAdapter(DocTopic).validate_python("supported_skus")


def test_v2_rejects_drift_and_unsafe_tool_contracts():
    good = load_contract(2)
    bad = deepcopy(good)
    bad["read_only"] = False
    with pytest.raises(ValueError, match="read-only"):
        validate_tool_contract(bad)
    bad = deepcopy(good)
    bad["tools"]["lookup_docs"]["arguments"]["topic"]["enum"].append("supported_skus")
    with pytest.raises(ValueError, match="DocTopic"):
        validate_tool_contract(bad)
    bad = deepcopy(good)
    bad["tools"]["lookup_docs"]["arguments"]["topic"]["enum"].append("images")
    with pytest.raises(ValueError, match="DocTopic"):
        validate_tool_contract(bad)
    bad = deepcopy(good)
    bad["tools"].pop("lookup_docs")
    with pytest.raises(ValueError, match="manifest"):
        validate_tool_contract(bad)


def test_sdk_exposes_enum_only_for_v2():
    # This test constructs agents offline; it never invokes the API.
    from sre_agent_evals.agent import build_agent

    for version in (1, 2, 3):
        prompt, tools = config_paths(version)
        agent = build_agent("gpt-4.1-mini", prompt_path=prompt, tools_path=tools)
        lookup = next(tool for tool in agent.tools if tool.name == "lookup_docs")
        schema = lookup.params_json_schema
        # SDK/Pydantic may represent the enum inline or behind a $ref.
        enums = []

        def collect(node):
            if isinstance(node, dict):
                if isinstance(node.get("enum"), list):
                    enums.append(set(node["enum"]))
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(schema)
        expected = set(get_args(DocTopic))
        if version >= 2:
            assert expected in enums
        else:
            assert expected not in enums
