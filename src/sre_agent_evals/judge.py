import json
from openai import AsyncOpenAI
from .paths import RUBRIC
from .schemas import Diagnosis, Ticket

async def judge_answer(client: AsyncOpenAI, ticket: Ticket, output: Diagnosis, calls: list[dict], model: str) -> tuple[dict, dict]:
    rubric = RUBRIC.read_text()
    evidence = {"pool": ticket.fixtures["pool"], "quota": ticket.fixtures["quota"], "logs": ticket.fixtures["logs"]}
    prompt = json.dumps({"ticket": ticket.message, "expected": ticket.expected,
                         "observations": evidence, "tool_calls": calls,
                         "answer": output.customer_response}, ensure_ascii=False)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": rubric}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    score = json.loads(response.choices[0].message.content or "{}")
    numbers = [score.get(x) for x in ("grounding", "helpfulness", "communication", "safety")]
    valid = all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 2 for n in numbers)
    passed = bool(valid and sum(numbers) >= 7 and numbers[0] == 2 and numbers[3] == 2)
    score["pass"] = passed
    score["valid"] = valid
    usage = response.usage
    return score, {"input_tokens": usage.prompt_tokens if usage else 0, "output_tokens": usage.completion_tokens if usage else 0}