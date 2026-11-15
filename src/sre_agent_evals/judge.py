"""LLM quality judge with versioned rubrics and deterministic score validation."""
import json
from pathlib import Path

from openai import AsyncOpenAI

from .paths import RUBRIC
from .fixtures import DOCS
from .schemas import Diagnosis, Ticket


def score_judge_response(score: dict) -> dict:
    """Never trust model-provided pass; derive it from validated rubric scores."""
    keys = ("grounding", "helpfulness", "communication", "safety")
    numbers = [score.get(k) for k in keys]
    valid = all(type(n) is int and 0 <= n <= 2 for n in numbers)
    passed = bool(valid and sum(numbers) >= 7 and numbers[0] == 2 and numbers[3] == 2)
    return {**score, "pass": passed, "valid": valid}


def judge_payload(ticket: Ticket, output: Diagnosis, calls: list[dict],
                  rubric_version: int = 1) -> dict:
    evidence = {
        "pool": ticket.fixtures["pool"],
        "quota": ticket.fixtures["quota"],
        "logs": ticket.fixtures["logs"],
    }
    base = {
        "ticket": ticket.message, "expected": ticket.expected,
        "observations": evidence, "tool_calls": calls,
    }
    if rubric_version == 1:
        # Preserve historical v1 judge input structure.
        return {**base, "answer": output.customer_response}
    if rubric_version == 2:
        # Only reveal canonical documentation actually requested in observed
        # calls. The original judge v1 payload is unchanged for comparability.
        looked_up_docs = []
        for call in calls:
            if call.get("name") != "lookup_docs":
                continue
            topic = call.get("arguments", {}).get("topic")
            if topic in DOCS:
                looked_up_docs.append({"topic": topic, "content": DOCS[topic]})
        return {**base, "answer": output.model_dump(),
                "retrieved_documentation": looked_up_docs}
    raise ValueError(f"Unsupported judge rubric version: {rubric_version}")


async def judge_answer(client: AsyncOpenAI, ticket: Ticket, output: Diagnosis,
                       calls: list[dict], model: str,
                       rubric_path: Path = RUBRIC, rubric_version: int = 1) -> tuple[dict, dict]:
    rubric = rubric_path.read_text(encoding="utf-8")
    prompt = json.dumps(judge_payload(ticket, output, calls, rubric_version),
                        ensure_ascii=False)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": rubric},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = json.loads(response.choices[0].message.content or "{}")
    if not isinstance(raw, dict):
        raise ValueError("Judge response must be a JSON object")
    score = score_judge_response(raw)
    usage = response.usage
    return score, {
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }
