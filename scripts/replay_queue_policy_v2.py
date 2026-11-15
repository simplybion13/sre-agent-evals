"""Opt-in, offline replay of saved candidates under versioned queue label policy V2.

Never modifies the frozen ticket dataset, saved responses, original grader or
V1 reports. V2 applies a fixture-driven policy independent of model predictions.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.graders import combined_solve, grade_labels, grade_tools
from sre_agent_evals.schemas import Diagnosis


def is_healthy_pool_saturation(ticket):
    """Backoff is not mandatory when healthy allocated slots are simply full."""
    if ticket.category != "queue" or ticket.expected["diagnosis"] != "queue_saturation":
        return False
    p = ticket.fixtures["pool"]
    q = ticket.fixtures["quota"]
    return (
        p.get("agent_state") == "healthy"
        and p.get("capacity_state") == "available"
        and p.get("running_jobs") == p.get("max_slots")
        and p.get("ready_agents") == p.get("max_slots")
        and p.get("queued_jobs", 0) > 0
        and q.get("remaining", 0) > 0
    )


def version2_ticket(ticket):
    """Return ticket with V2 required actions; never mutate input fixtures."""
    if not is_healthy_pool_saturation(ticket):
        return ticket
    expected = dict(ticket.expected)
    expected["required_actions"] = ["tune_concurrency"]
    return ticket.model_copy(update={"expected": expected})


def replay(rows, tickets):
    index = {t.id: t for t in tickets}
    out = []
    for row in rows:
        ticket = index[row["ticket_id"]]
        output = Diagnosis.model_validate(row["response"]) if row.get("response") else None
        # Catch dataset mismatch or corrupted saved traces before publishing a rescore.
        old_tools = grade_tools(ticket, row.get("tool_calls", []))
        old_labels = grade_labels(ticket, output)
        old_solved = bool(
            output is not None and not row.get("error")
            and combined_solve(old_tools, old_labels, row.get("judge_grade"))
        )
        if old_solved != row["solved"] or old_tools != row["tool_grade"] or old_labels != row["label_grade"]:
            raise ValueError(f"Frozen V1 reproduction mismatch on {row['ticket_id']}/{row['model']}")
        updated = version2_ticket(ticket)
        v2_labels = grade_labels(updated, output)
        v2_solved = bool(
            output is not None and not row.get("error")
            and combined_solve(old_tools, v2_labels, row.get("judge_grade"))
        )
        out.append({
            "ticket_id": ticket.id, "model": row["model"],
            "queue_policy_v2_applied": is_healthy_pool_saturation(ticket),
            "v1_required_actions": ticket.expected["required_actions"],
            "v2_required_actions": updated.expected["required_actions"],
            "v1_strict_solved": old_solved, "v2_strict_solved": v2_solved,
            "v1_label_grade": old_labels, "v2_label_grade": v2_labels,
        })
    return out


def summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"]].append(row)
    return {
        model: {
            "attempts": len(items),
            "v1_strict_solves": sum(r["v1_strict_solved"] for r in items),
            "v2_strict_solves": sum(r["v2_strict_solved"] for r in items),
            "changed_ticket_ids": sorted({
                r["ticket_id"] for r in items
                if r["v1_strict_solved"] != r["v2_strict_solved"]
            }),
        }
        for model, items in sorted(groups.items())
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--dataset", default=Path("data/tickets.jsonl"), type=Path)
    ap.add_argument("--output", default=Path("results/queue-policy-v2-replay.json"), type=Path)
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = replay(rows, load_tickets(args.dataset))
    payload = {
        "policy": "queue-actions-v2",
        "method": "offline saved-output replay; no candidate or judge API calls",
        "original_outputs_and_dataset_unchanged": True,
        "summary": summary(result),
        "rows": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
