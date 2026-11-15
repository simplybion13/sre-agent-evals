import json
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from agents import Agent, RunContextWrapper, function_tool
from .fixtures import DOCS, lookup_fixture
from .paths import PROMPT, TOOLS
from .schemas import Diagnosis, Ticket

@dataclass
class TicketContext:
    ticket: Ticket
    tool_calls: list[dict] = field(default_factory=list)


def build_agent(model: str, prompt_path: Path = PROMPT, tools_path: Path = TOOLS) -> Agent:
    """Prompts + tool specifications live outside code and are versioned independently."""
    spec = yaml.safe_load(tools_path.read_text())
    if spec["version"] != 1 or not spec["read_only"]:
        raise ValueError("Unexpected or non-read-only tool specification")
    definitions = spec["tools"]
    expected_names = {"query_pool_status", "read_recent_job_logs", "check_quota", "lookup_docs"}
    if set(definitions) != expected_names:
        raise ValueError("Tool manifest does not match tool implementation")

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

    @function_tool(name_override="lookup_docs", description_override=definitions["lookup_docs"]["description"])
    def lookup_docs(ctx: RunContextWrapper[TicketContext], topic: str) -> str:
        """Search relevant public product documentation by topic."""
        ctx.context.tool_calls.append({"name": "lookup_docs", "arguments": {"topic": topic}})
        return json.dumps({"topic": topic, "content": DOCS.get(topic, "No matching article")})

    return Agent(
        name="Nimbus pool support",
        model=model,
        instructions=prompt_path.read_text(),
        tools=[query_pool_status, read_recent_job_logs, check_quota, lookup_docs],
        output_type=Diagnosis,
    )