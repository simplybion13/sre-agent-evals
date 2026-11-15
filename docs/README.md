# Documentation

This repository evaluates a synthetic, read-only CI/CD build-pool support agent.
Start with the [project overview](../README.md) for the product question,
measured results, limitations, and runnable commands.

## Find what you need

| Question | Start here |
|---|---|
| How do I install the project and run tests? | [Quick start](../README.md#quick-start) |
| How does V4 gather evidence, keep it scoped, and produce an answer? | [Architecture and trust boundaries](architecture.md) |
| How are strict solves and model costs measured? | [Evaluation methodology](#evaluation-methodology) |
| What did the latest model comparison show? | [Current-model validation](current_model_validation_2026_11.md) |
| Why were the agent and evaluation designs changed? | [Architecture and Evaluation Decision Log](architecture_decision_log.md) |
| What changed in the queue-action grading policy? | [Queue-action policy V2](queue_action_policy_v2.md) |
| Where are the experiment versions and historical results? | [V1 to V4 evaluation history](../README.md#evaluation-history-v1--v2--v3--v4) |

## Architecture

The [architecture guide](architecture.md) describes the current V4 path,
including the exact trust boundaries between a customer ticket, observed
diagnostic data, the read-only controller, the model, the safety gate,
and independent grading. It also explains what the prototype does **not**
protect against.

The [decision log](architecture_decision_log.md) records the reasoning
behind changes, including the V3 regression and the move to controller-led
evidence collection. It is a record of design choices, not a substitute
for the implementation.

## Evaluation methodology

- **Frozen development set:** [50 synthetic tickets](../data/tickets.jsonl)
  with fixture data and labels. The candidate does not receive expected
  labels. See [ticket loading](../src/sre_agent_evals/fixtures.py).
- **Agent configuration:** [versioned prompts](../configs/prompts) and
  [tool contracts](../configs/tools). Versions V1 to V3 used model-selected
  read-only tools. V4 uses deterministic preflight evidence collection.
- **Objective checks:** [deterministic graders](../src/sre_agent_evals/graders.py)
  validate required read calls, ticket-scoped IDs, diagnosis, and required
  actions.
- **Response quality:** [LLM judge implementation](../src/sre_agent_evals/judge.py)
  uses [historical rubric V1](../evals/judge_rubric.md) by default. Judge
  rubrics V2 and V3 are separate experiments; changing the judge changes the
  interpretation of scores.
- **Combined strict solve:** a ticket must pass tool, diagnosis/action, and
  (when enabled) judge checks. The [runner](../src/sre_agent_evals/eval_runner.py)
  includes failed attempts in the denominator and records per-ticket traces,
  latency, tokens, and candidate inference cost.
- **Costs:** estimates use [versioned price inputs](../configs/pricing.json).
  They exclude the judge, live diagnostics, network/controller overhead,
  and support escalations.

## Experiments and decisions

The [README experiment history](../README.md#evaluation-history-v1--v2--v3--v4)
shows measured results and regressions. The
[current-model validation](current_model_validation_2026_11.md) compares
GPT-6 Luna and GPT-6.1 Sol on the same V4 synthetic development set.
The original 90% frozen-label solve rates are preserved alongside a
clearly identified, post-hoc score under [queue-action policy
V2](queue_action_policy_v2.md). A policy rescore is **not** new model
behavior.

## Reproduction

```powershell
python -m pip install -e ".[dev]"
pytest -q

# Requires OPENAI_API_KEY in your environment.
sre-eval --models gpt-6-luna gpt-6.1-sol --config-version 4 --judge-rubric-version 1 --limit 5 --output results/current-model-smoke
```

Inspect per-ticket records for API errors before a full run. Avoid
committing API keys or raw incident records. The fixture data here is
synthetic, not production customer information.
