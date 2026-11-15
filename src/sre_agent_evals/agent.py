import json
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from agents import Agent, RunContextWrapper, function_tool

from .contracts import validate_tool_contract
from .fixtures import DOCS, lookup_fixture
from .security import guarded_lookup
from .paths import PROMPT, TOOLS
from .schemas import Diagnosis, DocTopic, Ticket

@dataclass
class TicketContext:
    ticket: Ticket
    tool_calls: list[dict] = field(default_factory=list)


def build_agent(model: str, prompt_path: Path = PROMPT, tools_path: Path = TOOLS) -> Agent:
    """Construct one ticket-scoped agent from explicitly versioned prompt/tool files."""
    spec = yaml.safe_load(tools_path.read_text(encoding="utf-8"))
    version = validate_tool_contract(spec)
    definitions = spec["tools"]
    diagnostic_read = guarded_lookup if version >= 3 else lookup_fixture

    @function_tool(name_override="query_pool_status", description_override=definitions["query_pool_status"]["description"])
    def query_pool_status(ctx: RunContextWrapper[TicketContext], pool_id: str) -> str:
        """Inspect pool status for a customer-owned pool."""
        ctx.context.tool_calls.append({"name": "query_pool_status", "arguments": {"pool_id": pool_id}})
        return json.dumps(diagnostic_read(ctx.context.ticket, "pool", pool_id))

    @function_tool(name_override="read_recent_job_logs", description_override=definitions["read_recent_job_logs"]["description"])
    def read_recent_job_logs(ctx: RunContextWrapper[TicketContext], job_id: str) -> str:
        """Inspect sanitized job events by job ID."""
        ctx.context.tool_calls.append({"name": "read_recent_job_logs", "arguments": {"job_id": job_id}})
        return json.dumps(diagnostic_read(ctx.context.ticket, "logs", job_id))

    @function_tool(name_override="check_quota", description_override=definitions["check_quota"]["description"])
    def check_quota(ctx: RunContextWrapper[TicketContext], org_id: str) -> str:
        """Inspect the organization's active concurrency limit."""
        ctx.context.tool_calls.append({"name": "check_quota", "arguments": {"org_id": org_id}})
        return json.dumps(diagnostic_read(ctx.context.ticket, "quota", org_id))

    def read_docs(ctx: RunContextWrapper[TicketContext], topic: str) -> str:
        ctx.context.tool_calls.append({"name": "lookup_docs", "arguments": {"topic": topic}})
        return json.dumps({"topic": topic, "content": DOCS.get(topic, "No matching article")})

    if version >= 2:
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
