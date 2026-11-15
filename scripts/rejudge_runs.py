"""Opt-in judge-only replay of SAVED candidate outputs; original outcomes remain intact.

This avoids rerunning a stochastic candidate when testing judge changes.
Charges actual judge API calls. Does not overwrite input runs.jsonl.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

from openai import AsyncOpenAI
from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.judge import judge_answer
from sre_agent_evals.paths import JUDGE_RUBRICS
from sre_agent_evals.schemas import Diagnosis


def select_rows(rows, tickets, ticket_filter=None, candidate_model=None):
    by_id = {t.id: t for t in tickets}
    selected = []
    for row in rows:
        if ticket_filter and row.get("ticket_id") != ticket_filter:
            continue
        if candidate_model and row.get("model") != candidate_model:
            continue
        if row.get("response") is None:
            continue
        tid = row["ticket_id"]
        if tid not in by_id:
            raise ValueError(f"Ticket {tid} not found in provided --dataset")
        selected.append((row, by_id[tid]))
    return selected


async def run(args):
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for live judge-only replay")
    data = [json.loads(s) for s in args.runs.read_text(encoding="utf-8").splitlines()
            if s.strip()]
    selected = select_rows(data, load_tickets(args.dataset), args.ticket, args.candidate_model)
    if not selected:
        raise SystemExit("No matching saved candidate answers")
    client = AsyncOpenAI()
    results = []
    for row, ticket in selected:
        verdict, usage = await judge_answer(
            client, ticket, Diagnosis.model_validate(row["response"]),
            row.get("tool_calls") or [], args.judge_model,
            rubric_path=JUDGE_RUBRICS[args.rubric],
            rubric_version=args.rubric,
        )
        results.append({
            "ticket_id": ticket.id, "candidate_model": row["model"],
            "original_strict_solved": row.get("solved"),
            "original_judge_grade": row.get("judge_grade"),
            "replay_rubric_version": args.rubric,
            "replay_judge_grade": verdict,
            "replay_judge_usage": usage,
            "original_answer_unchanged": True,
        })
        print(f"{ticket.id}/{row['model']}: old={row.get('judge_grade',{}).get('pass')} new={verdict['pass']}")
    report = {
        "note": "Judge-only replay; does not change original strict solves or candidate outputs.",
        "rubric_version": args.rubric,
        "judge_model": args.judge_model,
        "count": len(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved judge-only replay: {args.output}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--rubric", type=int, choices=sorted(JUDGE_RUBRICS), default=3)
    p.add_argument("--judge-model", default="gpt-4.1")
    p.add_argument("--ticket", help="Optional ticket ID filter (e.g. A009)")
    p.add_argument("--candidate-model", help="Optional saved candidate model filter")
    p.add_argument("--output", type=Path, default=Path("results/judge-replay.json"))
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
