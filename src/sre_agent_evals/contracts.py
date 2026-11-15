"""Offline-validatable versioned tool contract (no OpenAI calls required)."""
from typing import get_args

from .schemas import DocTopic

EXPECTED_TOOLS = {"query_pool_status", "read_recent_job_logs", "check_quota", "lookup_docs"}


def validate_tool_contract(spec: dict) -> int:
    """Refuse invalid, writable, or mismatched tool definitions."""
    if not isinstance(spec, dict) or spec.get("version") not in (1, 2) or spec.get("read_only") is not True:
        raise ValueError("Unexpected or non-read-only tool specification")
    definitions = spec.get("tools")
    if not isinstance(definitions, dict) or set(definitions) != EXPECTED_TOOLS:
        raise ValueError("Tool manifest does not match tool implementation")
    if spec["version"] == 2:
        topic_spec = definitions["lookup_docs"].get("arguments", {}).get("topic", {})
        declared = topic_spec.get("enum")
        if (topic_spec.get("type") != "string"
                or not isinstance(declared, list)
                or len(declared) != len(set(declared))
                or set(declared) != set(get_args(DocTopic))):
            raise ValueError("v2 doc topic enum must match DocTopic exactly")
    return spec["version"]
