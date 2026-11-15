import argparse
import asyncio
import os

from agents import Runner

from .agent import TicketContext, build_agent
from .fixtures import load_tickets
from .paths import DEFAULT_CONFIG_VERSION, SUPPORTED_CONFIG_VERSIONS, config_paths


async def run_one(ticket_id: str, model: str, config_version: int):
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first")
    ticket = next((x for x in load_tickets() if x.id == ticket_id), None)
    if ticket is None:
        raise SystemExit(f"Unknown ticket ID: {ticket_id}")
    prompt_path, tools_path = config_paths(config_version)
    ctx = TicketContext(ticket)
    model_input = ticket.message
    bundle = None
    if config_version == 4:
        from .orchestration import collect_evidence, enforce_missing_job_boundary
        bundle = collect_evidence(ticket)
        ctx.tool_calls.extend(bundle.calls)
        model_input = bundle.model_input(ticket.message)
    result = await Runner.run(
        build_agent(model, prompt_path=prompt_path, tools_path=tools_path),
        model_input,
        context=ctx,
        max_turns=8,
    )
    output = result.final_output
    if bundle is not None:
        output, audit = enforce_missing_job_boundary(ticket, bundle, output)
        print("Controller safety gate:", audit)
    print(output.model_dump_json(indent=2))
    print("\nObserved tool calls:", ctx.tool_calls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", default="T001")
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--config-version", type=int, default=DEFAULT_CONFIG_VERSION,
                    choices=SUPPORTED_CONFIG_VERSIONS)
    args = ap.parse_args()
    asyncio.run(run_one(args.ticket, args.model, args.config_version))


if __name__ == "__main__":
    main()
