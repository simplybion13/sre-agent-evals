import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

import yaml
from agents import Agent, RunContextWrapper, function_tool

from .fixtures import DOCS, lookup_fixture
from .paths import PROMPT, TOOLS
from .schemas import Diagnosis, DocTopic, Ticket

EXPECTED_TOOLS = {"query_pool_status", "read_recent_job_logs", "check_quota", "lookup_docs"}


@dataclass
class TicketContext:
    ticket: Ticket
    tool_calls: list[dict] = field(default_factory=list)


def validate_tool_contract(spec: dict) -> int:
    """Refuse invalid or mismatched tool contracts instead of silently falling back."""
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


def build_agent(model: str, prompt_path: Path = PROMPT, tools_path: Path = TOOLS) -> Agent:
    """Construct one ticket-scoped agent from explicitly versioned prompt/tool files."""
    spec = yaml.safe_load(tools_path.read_text(encoding="utf-8"))
    version = validate_tool_contract(spec)
    definitions = spec["tools"]

    @function_tool(name_override="query_pool_status", description_override=definitions["query_pool_status"]["description"])
    def query_pool_status(ctx: RunContextWrapper[TicketContext], pool_id: str) -> str:
        """Inspect pool status for a customer-owned pool."""
        ctx.context.tool_calls.append({"name": "query_pool_status", "arguments": {"pool_id": pool_id}})
        return json.dumps(lookup_fixture(ctx.context.ticket, "pool", pool_id))

    @function_tool(name_override="read_recent_job_logs", description_override=definitions["read_recent_job_logs"]["description"])
    def read_recent_job_logs(ctx: RunContextWrapper[TicketContext], job_id: str) -> str:
        """Inspect sanitized job events by job ID."""
        ctx.context.tool_calls.append({"name": "read_recent_job_logs", "arguments": {"job_id": job_id}})
        return json.dumps(lookup_fixture(ctx.context.ticket, "logs", job_id))

    @function_tool(name_override="check_quota", description_override=definitions["check_quota"]["description"])
    def check_quota(ctx: RunContextWrapper[TicketContext], org_id: str) -> str:
        """Inspect the organization's active concurrency limit."""
        ctx.context.tool_calls.append({"name": "check_quota", "arguments": {"org_id": org_id}})
        return json.dumps(lookup_fixture(ctx.context.ticket, "quota", org_id))

    def read_docs(ctx: RunContextWrapper[TicketContext], topic: str) -> str:
        ctx.context.tool_calls.append({"name": "lookup_docs", "arguments": {"topic": topic}})
        return json.dumps({"topic": topic, "content": DOCS.get(topic, "No matching article")})

    if version == 2:
        # Literal produces a JSON Schema enum in the SDK function tool; an invalid topic
        # is rejected by argument validation instead of reaching the mock docs store.
        @function_tool(name_override="lookup_docs", description_override=definitions["lookup_docs"]["description"])
        def lookup_docs(ctx: RunContextWrapper[TicketContext], topic: DocTopic) -> str:
            """Read one canonical documentation section."""
            return read_docs(ctx, topic)
    else:
        # Keep the baseline v1 tool shape reproducible for before/after evaluations.
        @function_tool(name_override="lookup_docs", description_override=definitions["lookup_docs"]["description"])
        def lookup_docs(ctx: RunContextWrapper[TicketContext], topic: str) -> str:
            """Read a documentation topic (baseline v1 free text)."""
            return read_docs(ctx, topic)

    return Agent(
        name="Nimbus pool support",
        model=model,
        instructions=prompt_path.read_text(encoding="utf-8"),
        tools=[query_pool_status, read_recent_job_logs, check_quota, lookup_docs],
        output_type=Diagnosis,
    )
