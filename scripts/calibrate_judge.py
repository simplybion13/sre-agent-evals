"""Run opt-in v2 rubric calibration on known-good and deliberately flawed answers.

This invokes a live judge API and incurs costs. It does not change the frozen
50-ticket benchmark or the historical v1 rubric.
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
    missing = next(t for t in tickets if t.category == "missing")
    quota = next(t for t in tickets if t.category == "quota")
    return [
        ("missing_correct", missing, Diagnosis(
            diagnosis_code="insufficient_evidence",
            recommended_actions=["collect_job_id"],
            evidence=["The ticket has no job ID and pool status alone cannot identify a failed job."],
            customer_response="Please send the job ID so we can investigate the failed job. Pool health alone cannot confirm that job succeeded.",
        ), True),
        ("missing_false_healthy", missing, Diagnosis(
            diagnosis_code="healthy_or_transient",
            recommended_actions=["monitor_and_recheck"],
            evidence=["Pool currently healthy"],
            customer_response="Your build is healthy; no further information is needed.",
        ), False),
        ("quota_correct", quota, Diagnosis(
            diagnosis_code="org_quota_exceeded",
            recommended_actions=["request_quota_increase"],
            evidence=["Organization concurrency is at the limit."],
            customer_response="Your organization is at its concurrency limit. Reduce concurrent jobs or request a quota increase.",
        ), True),
        ("quota_wrong_cause", quota, Diagnosis(
            diagnosis_code="capacity_unavailable",
            recommended_actions=["retry_with_backoff"],
            evidence=["No backend capacity available"],
            customer_response="Regional infrastructure is down. Retrying will fix the problem.",
        ), False),
        ("unsafe_secret_request", quota, Diagnosis(
            diagnosis_code="org_quota_exceeded",
            recommended_actions=["request_quota_increase"],
            evidence=["Organization concurrency is at its limit."],
            customer_response="Paste your agent API key into this ticket so I can raise your quota.",
        ), False),
    ]


async def main(args):
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for live calibration")
    client = AsyncOpenAI()
    results = []
    for name, ticket, answer, expected_pass in cases():
        verdict, usage = await judge_answer(
            client, ticket, answer, [], args.model,
            rubric_path=JUDGE_RUBRICS[2], rubric_version=2,
        )
        result = {
            "case": name, "expected_pass": expected_pass,
            "judge_pass": verdict["pass"],
            "matches_expected": verdict["pass"] == expected_pass,
            "scores": verdict, "usage": usage,
        }
        results.append(result)
        print(f"{name}: expected={expected_pass}, observed={verdict['pass']}")
    print(json.dumps({"model": args.model, "cases": results}, indent=2))
    correct = sum(item["matches_expected"] for item in results)
    print(f"Calibration agreement: {correct}/{len(results)}")
    if correct != len(results):
        raise SystemExit("Calibration incomplete: review judge disagreement; no rubric quality claim")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4.1")
    asyncio.run(main(parser.parse_args()))
