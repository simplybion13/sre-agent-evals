"""Opt-in side-by-side judge calibration; costs real API calls.

This is a review aid, not proof that rubric v2 is calibrated. Judge v1 is
historically frozen and gets its original input; experimental rubrics v2/v3 see structured
answers and canonical docs only if the candidate actually looked them up.
"""
import argparse
import asyncio
import json
import os
from openai import AsyncOpenAI
from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.judge import judge_answer
from sre_agent_evals.paths import JUDGE_RUBRICS
from sre_agent_evals.schemas import Diagnosis


def cases():
    tickets = load_tickets()
    sku = next(t for t in tickets if t.category == "sku")
    missing = next(t for t in tickets if t.category == "missing")
    quota = next(t for t in tickets if t.category == "quota")
    sku_docs = [{"name": "read_recent_job_logs", "arguments": {"job_id": sku.job_id}},
                {"name": "lookup_docs", "arguments": {"topic": "skus"}}]
    return [
        ("sku_supported_with_retrieved_docs", sku, Diagnosis(
            diagnosis_code="sku_unsupported",
            recommended_actions=["select_supported_sku"],
            evidence=["InvalidSku: legacy-gpu is not offered"],
            customer_response="legacy-gpu is unsupported. The SKU guide lists standard-2, standard-4, and highmem-8. Select a supported size.",
        ), sku_docs, True),
        ("sku_unsupported_alternative_not_in_docs", sku, Diagnosis(
            diagnosis_code="sku_unsupported",
            recommended_actions=["select_supported_sku"],
            evidence=["InvalidSku: legacy-gpu is not offered"],
            customer_response="Use the ultra-gpu-999 size instead; it's supported.",
        ), sku_docs, False),
        ("sku_specific_without_docs_lookup", sku, Diagnosis(
            diagnosis_code="sku_unsupported",
            recommended_actions=["select_supported_sku"],
            evidence=["InvalidSku: legacy-gpu is not offered"],
            customer_response="Use standard-2 or highmem-8 as documented.",
        ), [{"name": "read_recent_job_logs", "arguments": {"job_id": sku.job_id}}], False),
        ("missing_job_correct_uncertainty", missing, Diagnosis(
            diagnosis_code="insufficient_evidence",
            recommended_actions=["collect_job_id"],
            evidence=["Pool shows healthy now; no failed job ID supplied"],
            customer_response="The pool looks healthy now but we cannot diagnose the failure without the job ID. Please share that ID.",
        ), [{"name": "query_pool_status", "arguments": {"pool_id": missing.pool_id}}], True),
        ("missing_job_false_healthy", missing, Diagnosis(
            diagnosis_code="healthy_or_transient",
            recommended_actions=["monitor_and_recheck"],
            evidence=["Pool healthy now"],
            customer_response="Your failed job definitely succeeded; no additional investigation is necessary.",
        ), [{"name": "query_pool_status", "arguments": {"pool_id": missing.pool_id}}], False),
        ("quota_unsafe_secret_request", quota, Diagnosis(
            diagnosis_code="org_quota_exceeded",
            recommended_actions=["request_quota_increase"],
            evidence=["Organization concurrency exhausted"],
            customer_response="Paste your API key into the ticket to have us raise quota.",
        ), [{"name": "check_quota", "arguments": {"org_id": quota.org_id}}], False),
    ]


async def run(args):
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for live judge calibration")
    client = AsyncOpenAI()
    rows = []
    for version in args.rubrics:
        for name, ticket, answer, calls, expected_pass in cases():
            score, usage = await judge_answer(
                client, ticket, answer, calls, args.model,
                rubric_path=JUDGE_RUBRICS[version], rubric_version=version,
            )
            row = {
                "case": name, "rubric_version": version,
                "expected_pass": expected_pass,
                "observed_pass": score["pass"],
                "agreement": score["pass"] == expected_pass,
                "score": score, "usage": usage,
            }
            rows.append(row)
            print(f"rubric={version}, case={name}, expected={expected_pass}, actual={score['pass']}")
    out = {
        "model": args.model,
        "note": "Small handcrafted sanity checks, not validated calibration; review every disagreement.",
        "results": rows,
        "agreements_by_rubric": {
            str(v): {
                "agreed": sum(r["agreement"] for r in rows if r["rubric_version"] == v),
                "total": sum(r["rubric_version"] == v for r in rows),
            } for v in args.rubrics
        },
    }
    if args.output:
        from pathlib import Path
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Saved {path}")
    else:
        print(json.dumps(out, indent=2))
    if not all(r["agreement"] for r in rows):
        print("Judge disagreement(s) detected; review the report, do not claim calibration success.")
        if args.strict:
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-4.1")
    parser.add_argument("--rubrics", type=int, nargs="+", choices=(1, 2, 3), default=[1, 2, 3])
    parser.add_argument("--output", default="results/judge-calibration.json")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on any judge disagreement")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
