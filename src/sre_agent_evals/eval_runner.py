"""Compare two OpenAI Agents SDK models on the same hidden-label tickets."""
import argparse
import asyncio
import csv
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from .fixtures import load_tickets
from .graders import audit_queue_actions, combined_solve, grade_labels, grade_tools
from .paths import PRICING, DEFAULT_CONFIG_VERSION, SUPPORTED_CONFIG_VERSIONS, JUDGE_RUBRICS, config_paths
from .schemas import Diagnosis


def estimate_cost(model: str, input_tokens: int, output_tokens: int, pricing: dict) -> float | None:
    rate = pricing["models"].get(model)
    if not rate:
        return None
    return (input_tokens * rate["input_per_million"] + output_tokens * rate["output_per_million"]) / 1_000_000


async def evaluate_one(agent, ticket, model: str, judge_client, judge_model: str | None, prices,
                       rubric_version: int = 1, config_version: int = 3):
    from agents import Runner
    from .agent import TicketContext
    from .judge import judge_answer
    ctx = TicketContext(ticket)
    t0 = time.perf_counter()
    output = None
    raw_output = None
    correction = {"applied": False}
    error = None
    input_tokens = output_tokens = 0
    try:
        if config_version == 4:
            from .orchestration import collect_evidence, enforce_missing_job_boundary
            bundle = collect_evidence(ticket)
            ctx.tool_calls.extend(bundle.calls)
            model_input = bundle.model_input(ticket.message)
        else:
            bundle = None
            model_input = ticket.message
        result = await Runner.run(agent, model_input, context=ctx, max_turns=8)
        raw_output = Diagnosis.model_validate(result.final_output)
        output = raw_output
        if bundle is not None:
            output, correction = enforce_missing_job_boundary(ticket, bundle, raw_output)
        usage = result.context_wrapper.usage
        input_tokens, output_tokens = usage.input_tokens, usage.output_tokens
    except Exception as exc:  # include failures in denominator, not just successful completions
        error = f"{type(exc).__name__}: {exc}"
    latency_s = time.perf_counter() - t0
    tool_grade = grade_tools(ticket, ctx.tool_calls)
    label_grade = grade_labels(ticket, output)
    judge_grade, judge_usage, judge_error = None, None, None
    if judge_model and output is not None:
        try:
            judge_grade, judge_usage = await judge_answer(judge_client, ticket, output, ctx.tool_calls, judge_model,
                                                        rubric_path=JUDGE_RUBRICS[rubric_version],
                                                        rubric_version=rubric_version)
        except Exception as exc:
            judge_error = f"{type(exc).__name__}: {exc}"
            # Fail closed: missing judge verdict must not create a false solve.
            judge_grade = {"pass": False, "error": judge_error}
    return {
        "ticket_id": ticket.id, "category": ticket.category, "model": model,
        "expected_diagnosis": ticket.expected["diagnosis"],
        "predicted_diagnosis": output.diagnosis_code if output else None,
        "response": output.model_dump() if output else None,
        "raw_response": raw_output.model_dump() if raw_output and config_version == 4 else None,
        "controller_correction": correction if config_version == 4 else None,
        "tool_call_origin": "deterministic_preflight" if config_version == 4 else "model_tool_calls",
        "tool_calls": ctx.tool_calls, "tool_grade": tool_grade,
        "label_grade": label_grade, "queue_action_audit": audit_queue_actions(ticket, output),
        "judge_grade": judge_grade,
        "judge_error": judge_error, "judge_usage": judge_usage,
        "solved": bool(output is not None and not error and combined_solve(tool_grade, label_grade, judge_grade)),
        "latency_s": round(latency_s, 3), "input_tokens": input_tokens,
        "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens,
        "agent_cost_usd": estimate_cost(model, input_tokens, output_tokens, prices),
        "error": error,
    }


def summarize(rows: list[dict]) -> list[dict]:
    models = sorted({r["model"] for r in rows})
    out = []
    for model in models:
        r = [x for x in rows if x["model"] == model]
        avg_costs = [x["agent_cost_usd"] for x in r if x["agent_cost_usd"] is not None]
        out.append({
            "model": model, "tickets": len(r),
            "solve_rate_pct": round(100 * sum(x["solved"] for x in r) / len(r), 1),
            "tool_pass_pct": round(100 * sum(x["tool_grade"]["pass"] for x in r) / len(r), 1),
            "diagnosis_pct": round(100 * sum(x["label_grade"]["diagnosis_correct"] for x in r) / len(r), 1),
            "avg_latency_s": round(statistics.mean(x["latency_s"] for x in r), 2),
            "p95_latency_s": round(sorted(x["latency_s"] for x in r)[max(0, int(0.95 * len(r) + 0.9999) - 1)], 2),
            "avg_input_tokens": round(statistics.mean(x["input_tokens"] for x in r)),
            "avg_output_tokens": round(statistics.mean(x["output_tokens"] for x in r)),
            "avg_total_tokens": round(statistics.mean(x["total_tokens"] for x in r)),
            "avg_cost_usd": round(statistics.mean(avg_costs), 6) if len(avg_costs) == len(r) else None,
        })
    return out


def markdown_table(summary: list[dict]) -> str:
    heads = ["Model", "Tickets", "Solve %", "Tool pass %", "Diagnosis %", "Avg latency s", "P95 s", "Avg in tokens", "Avg out tokens", "Avg total tokens", "Avg $/ticket"]
    lines = ["| " + " | ".join(heads) + " |", "|" + "|".join(["---"] * len(heads)) + "|"]
    for r in summary:
        vals = [r["model"], str(r["tickets"]), str(r["solve_rate_pct"]), str(r["tool_pass_pct"]),
                str(r["diagnosis_pct"]), str(r["avg_latency_s"]), str(r["p95_latency_s"]),
                str(r["avg_input_tokens"]), str(r["avg_output_tokens"]), str(r["avg_total_tokens"]),
                f'${r["avg_cost_usd"]:.6f}' if r["avg_cost_usd"] is not None else "N/A"]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


async def run(args):
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for a live evaluation; see .env.example")
    if len(set(args.models)) != 2:
        raise SystemExit("Pass exactly two distinct models")
    tickets = load_tickets(Path(args.dataset))
    if args.limit:
        tickets = tickets[:args.limit]
    prices = json.loads(PRICING.read_text())
    if any(model not in prices["models"] for model in args.models):
        raise SystemExit("Both models must have prices in configs/pricing.json; add them before comparing cost")
    from .agent import build_agent
    prompt_path, tools_path = config_paths(args.config_version)
    agent_by_model = {name: build_agent(name, prompt_path=prompt_path, tools_path=tools_path) for name in args.models}
    if not args.no_judge:
        from openai import AsyncOpenAI
    judge_client = AsyncOpenAI() if not args.no_judge else None
    judge_model = None if args.no_judge else args.judge_model
    # Sequential runs make API throttling and per-ticket latency easier to interpret.
    rows = []
    for ticket in tickets:
        for model in args.models:
            print(f"Evaluating {ticket.id} / {model} ...", flush=True)
            row = await evaluate_one(agent_by_model[model], ticket, model, judge_client, judge_model, prices,
                                     rubric_version=args.judge_rubric_version,
                                     config_version=args.config_version)
            rows.append(row)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary = summarize(rows)
    with (out / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    meta = {"created_at": datetime.now(timezone.utc).isoformat(), "models": args.models,
            "judge_model": judge_model, "judge_rubric_version": args.judge_rubric_version,
            "dataset": args.dataset, "tickets_per_model": len(tickets),
            "config_version": args.config_version,
            "evidence_collection": "deterministic_preflight" if args.config_version == 4 else "model_tool_calls",
            "controller_safety_gate": args.config_version == 4,
            "prompt_path": str(prompt_path),
            "tool_contract_path": str(tools_path),
            "pricing_checked_on": prices["checked_on"],
            "note": "Cost and token columns exclude judge calls; latency measures agent only. Judge usage in runs.jsonl."}
    report = "# Evaluation report\n\n" + markdown_table(summary) + "\n\n" + json.dumps(meta, indent=2) + "\n"
    (out / "report.md").write_text(report)
    print("\n" + report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs=2, default=["gpt-4.1-mini", "gpt-4.1"])
    parser.add_argument("--dataset", default=str(Path(__file__).resolve().parents[2] / "data" / "tickets.jsonl"))
    parser.add_argument("--config-version", type=int, default=DEFAULT_CONFIG_VERSION,
                        choices=SUPPORTED_CONFIG_VERSIONS)
    parser.add_argument("--judge-model", default="gpt-4.1")
    parser.add_argument("--judge-rubric-version", type=int, choices=sorted(JUDGE_RUBRICS), default=1)
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge; solve uses deterministic graders only")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default="results")
    args = parser.parse_args()
    asyncio.run(run(args))

if __name__ == "__main__":
    main()