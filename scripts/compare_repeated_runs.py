"""Compare repeated independent run JSONL files without changing strict scores.

Usage: python scripts/compare_repeated_runs.py results/run-a/runs.jsonl results/run-b/runs.jsonl
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def compare(paths):
    outcomes = defaultdict(list)
    run_models = {}
    for path in paths:
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        seen = set()
        for record in entries:
            key = (record["ticket_id"], record["model"])
            if key in seen:
                raise ValueError(f"Duplicate record {key} in {path}")
            seen.add(key)
            outcomes[key].append(bool(record["solved"]))
        run_models[str(path)] = len(seen)
    expected = len(paths)
    if any(len(outcomes[key]) != expected for key in outcomes):
        raise ValueError("Runs have different ticket/model sets; cannot compare")
    per_model = defaultdict(lambda: {"tickets": 0, "always_solved": 0,
                                    "never_solved": 0, "variable": 0})
    disagreements = []
    for (ticket, model), values in sorted(outcomes.items()):
        record = per_model[model]
        record["tickets"] += 1
        if all(values):
            record["always_solved"] += 1
        elif not any(values):
            record["never_solved"] += 1
        else:
            record["variable"] += 1
            disagreements.append({"ticket_id": ticket, "model": model, "solved_by_run": values})
    return {
        "run_files": [str(p) for p in paths],
        "runs": len(paths),
        "per_model": dict(per_model),
        "variable_tickets": disagreements,
        "note": "Repeated synthetic runs, not independent samples or formal confidence intervals.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("runs", nargs="+", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if len(args.runs) < 2:
        p.error("Pass two or more independent runs.jsonl files")
    report = compare(args.runs)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
