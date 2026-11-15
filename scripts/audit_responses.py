"""Optional audit of existing runs.jsonl; does NOT recompute historical solves.

Usage: python scripts/audit_responses.py --runs results/v4-challenge-v1/runs.jsonl
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from sre_agent_evals.response_audit import audit_response
from sre_agent_evals.schemas import Diagnosis


def inspect(rows):
    audited = []
    counts = Counter()
    for row in rows:
        response = row.get("response")
        if response is None:
            continue
        audit = audit_response(Diagnosis.model_validate(response), row.get("tool_calls") or [])
        counts.update(f["code"] for f in audit["findings"])
        audited.append({
            "ticket_id": row["ticket_id"],
            "model": row["model"],
            "original_solved": row.get("solved"),
            "audit": audit,
        })
    return {
        "note": "Advisory only; no grades changed. Manual review required.",
        "inspected": len(audited),
        "flagged": sum(not r["audit"]["pass_advisory"] for r in audited),
        "finding_counts": dict(counts),
        "reviews": audited,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    rows = [json.loads(x) for x in args.runs.read_text(encoding="utf-8").splitlines() if x.strip()]
    result = inspect(rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "reviews"}, indent=2))
    if args.output:
        print(f"Review details saved to {args.output}")


if __name__ == "__main__":
    main()
