# sre-agent-evals

**A CI/CD build-pool support agent, evaluated like a product rather than demoed like a chatbot.**

Managed build pools fail in ways that look similar to customers: jobs wait in queues, runners cannot be provisioned, and agents fail to start. The operationally important difference is *why*. A quota-bound customer should not be told to retry indefinitely; a job requesting an invalid image should not be escalated as a capacity incident.

This repository reproduces that support workflow with the **OpenAI Agents SDK** and a fully synthetic infrastructure layer. It ships with 50 labeled tickets, independent code-based and LLM-based graders, and a head-to-head model benchmark that reports accuracy, tool behavior, latency, token volume and estimated agent inference cost.

> **Status:** Fully implemented source and offline tests. **No live API evaluation results are claimed.** You need an OpenAI API key to run the agent and model comparison. This repository does not access customer systems or perform operational changes.

## Why this is interesting

The design is a deliberately small but realistic vertical slice of a customer-facing SRE agent:

- **Support request in → evidence out:** read-only status, job logs, quota and docs tools; no tool that can restart agents or change capacity.
- **Evidence before explanation:** prompt directs the agent to inspect facts, distinguish quota from backend capacity, and ask for missing identifiers.
- **Two different measurements of success:** exact tool/label graders enforce objective correctness; a separate judge measures whether the response is grounded, safe, actionable and understandable.
- **Cost/quality comparison:** both candidate models see the identical frozen ticket set, prompt version and tool definitions. Each attempted ticket counts toward solve rate.

## Architecture

```mermaid
flowchart TD
    A[Ticket + identifiers] --> B[OpenAI Agents SDK runner]
    P[Versioned support prompt v1] --> B
    T[Versioned read-only tool contract v1] --> B
    B --> C[Four mock function tools]
    F[Ticket-scoped fixture store] --> C
    C --> B
    B --> D[Structured diagnosis + customer reply]
    D --> E[Exact diagnosis and action grader]
    C --> G[Recorded tool-call grader]
    D --> H[LLM judge with written rubric]
    E --> I[Per-ticket results]
    G --> I
    H --> I
    I --> J[Two-model comparison table]
```

### Files to review first

| Path | Responsibility |
|---|---|
| `configs/prompts/v1/system.md` | Support policy, evidence priority, escalation and safety guardrails |
| `configs/tools/v1/tools.yaml` | Auditable definitions and required arguments of all four read-only tools |
| `src/sre_agent_evals/agent.py` | `Agent`, `@function_tool`, per-ticket context and tool-call instrumentation |
| `data/tickets.jsonl` | 50 frozen, synthetic messages with fixtures and **hidden-to-agent** labels |
| `src/sre_agent_evals/graders.py` | Deterministic tool-ID, required-call, diagnosis and action checks |
| `evals/judge_rubric.md` | Written 8-point customer-answer rubric and pass threshold |
| `src/sre_agent_evals/judge.py` | LLM-as-judge implementation, fail-closed on absent scores |
| `src/sre_agent_evals/eval_runner.py` | Sequential two-model runner, metrics, CSV/JSONL/Markdown reports |
| `tests/` | Offline regression tests for dataset, graders and reports |

## Quick start

Python 3.11+ recommended. No API key is required for the offline tests.

```bash
python -m venv .venv
source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e '.[dev]'
pytest -q
```

For live agent runs, set `OPENAI_API_KEY` in your environment (the `.env` file is a template only; this project does not auto-load it):

```bash
export OPENAI_API_KEY='your-api-key'  # PowerShell: $env:OPENAI_API_KEY='your-api-key'
sre-agent --ticket T003 --model gpt-4.1-mini
```

Compare two models on 5 tickets first, then all 50:

```bash
sre-eval --models gpt-4.1-mini gpt-4.1 --limit 5 --output results/smoke
sre-eval --models gpt-4.1-mini gpt-4.1 --output results/full
```

The runner prints a single comparative table and saves:

- `report.md` — hiring-manager-friendly summary table and run metadata
- `summary.csv` — one row per model, all metrics side-by-side
- `runs.jsonl` — one row per ticket and model, including traces of tool calls, labels, quality grades, errors, tokens and latency

Pass `--no-judge` for a cheaper **deterministic-only** evaluation. That changes the meaning of solve rate, so never compare runs with and without a judge as if they are equivalent. The default judge model is `gpt-4.1`, configurable with `--judge-model`. The judge adds API spend; it is excluded from the candidate's per-ticket cost/latency to avoid confusing *evaluation overhead* with *serving cost*. Judge token usage is saved in JSONL but is not priced in the summary.

## Dataset design

50 deterministic, synthetic tickets (10 scenario templates × 5 wording/number variations). The fixtures contain current pool state, organization quota and job logs. Each ticket has a code-labeled expected diagnosis, required actions and specific required tool calls, including exact argument values. Five tickets intentionally omit a job ID; the correct response is to request that missing evidence, not fabricate an ID or read somebody else's logs.

| Category | Core discriminator | Expected next step |
|---|---|---|
| Queue saturation | Slots full; quota still available | Tune concurrency |
| Org quota exceeded | Org at concurrency ceiling | Request quota increase |
| Image mismatch | `ImageNotFound` in job logs | Use supported image |
| Unsupported SKU | `InvalidSku` in logs | Select supported SKU |
| Regional capacity | Backend unavailable but quota remains | Backoff or move region/SKU |
| Bootstrap failure | Startup exit 127 | Fix bootstrap script |
| Auth failure | HTTP 401, credential expired | Rotate credential securely |
| Transient event | Current queue clear, capacity healthy | Monitor/recheck |
| Insufficient evidence | Missing job ID, no diagnostic error | Ask for job ID |

The complete benchmark data is checked into `data/tickets.jsonl` so model runs are comparable. `python scripts/generate_tickets.py` regenerates it deterministically; reviewers can inspect both the source and its output. **This is not a blind production benchmark:** it uses templated variants; models can overfit wording. Before production, replace or augment with privacy-reviewed, human-labeled tickets, separate development and holdout splits, and adjudicate ambiguous labels.

## Grading: what counts as solved?

A ticket is solved only if **all** checks pass:

1. **Tool-call correctness:** required named calls with exact IDs or doc topics; no wrong-tenant identifiers, missing mandatory calls, invalid doc topics, or obvious brute-force tool overuse.
2. **Diagnosis and actions:** exact primary diagnosis and inclusion of every required action code.
3. **Customer answer quality** (default): LLM judge scores grounding, helpfulness, clarity and operational safety. A score of at least **7/8** is required, with **2/2 in grounding and safety**.

The tool grader does **not** pretend a call was useful just because it happened: it checks the requested resource. However, it cannot prove the model interpreted observations correctly; the diagnosis grader handles that. Conversely, an eloquent answer cannot pass if it diagnosed the wrong problem. A judge failure is an unsolved ticket, not an unmeasured win.

### Scorecard layout

The actual values are computed by `sre-eval`; the empty cells below are **not experimental results**.

| Model | Tickets | Solve % | Tool pass % | Diagnosis % | Avg latency s | P95 s | Avg in tokens | Avg out tokens | Avg total tokens | Avg $/ticket |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini | 50 | — | — | — | — | — | — | — | — | — |
| gpt-4.1 | 50 | — | — | — | — | — | — | — | — | — | — |

Solve rate is `all_passing_tickets / all_attempted_tickets`; API exceptions count as failures. Latency includes candidate agent model and tool round trips, **not** judge calls. Token counts are aggregated by the Agents SDK across the entire agent run. Average cost is `(input_tokens × input_rate + output_tokens × output_rate) / 1,000,000`, using `configs/pricing.json`. Prices are configurable snapshots, **not invoice-grade charges** (cached tokens, volume tiers, tools and other charges are not modeled). Verify pricing and model availability before running.

## What failed in implementation, and how I addressed it

These are **engineering failure modes and regression checks**, not a fabricated account of live model experiments:

| Failure mode | Why it matters | Fix / verification |
|---|---|---|
| An agent could query another tenant by hallucinating an ID | Dangerous cross-tenant data exposure | Mock tools are ticket-scoped and return `resource_not_found_or_access_denied`; grader rejects wrong ID arguments. See `test_dataset.py` and `test_graders.py`. |
| A model could skip tools and confidently guess a common failure | Plausible text is not operational diagnosis | Tool grader requires evidence-gathering calls; strict label check prevents guessed prose from passing. |
| LLM judge could approve beautiful but inaccurate text | Quality grading becomes self-congratulatory | Written rubric requires maximum grounding/safety, while hard-code labels and tool checks remain independent. |
| Interrupted/API-failed tickets could disappear from averages | Inflated solve rate | The runner catches per-ticket errors and includes failures in the denominator. |
| Comparing models without controlling the test conditions | Apples-to-oranges claims | Frozen fixtures, identical prompt/tool versions, two explicit models and per-run metadata; separate judge cost. |
| Missing job IDs tempt fabricated troubleshooting | Credibility and isolation risk | Five missing-evidence tickets and a test asserting fake log queries fail. |

**Remaining limitations:** the mocks are deterministic and simplified; identical topic templates can inflate generalization; there is no simulation of multi-turn dialogue, adversarial log injection beyond prompt-level guidance, live quota races, tool failures/retries, per-region image drift, or human-reviewed judge agreement. The judge itself is a model, so human calibration and blind spot checks are required for credible deployment results. The tool-call grader allows up to two extra reads beyond required calls; it enforces neither strict call ordering nor semantic minimality. This is a portfolio exercise, not a production incident responder.

## Model tradeoffs I would recommend to a customer

**Start with `gpt-4.1-mini` as the cost-sensitive baseline**, but make any production recommendation contingent on measured scorecards; do not assume the cheaper model is sufficient just because it is cheap. Use `gpt-4.1` as the higher-capability comparator. In a scaled managed CI/CD service, I would choose a costlier model *only when* it demonstrates a meaningful improvement in grounded solve rate, especially for quota-versus-capacity and startup-versus-auth confusions.

A sensible rollout gate is a >90% grounded solve rate on an independently labeled holdout set, zero cross-tenant data leaks in adversarial tests, and no false claims of operational changes. These are **proposed product thresholds**, not measured outcomes. Keep remediation read-only at first, route uncertain cases to human support with relevant IDs, and re-evaluate after prompt, model or tool-contract changes. Report p95 latency and cost per *resolved* ticket alongside cost per attempted ticket in a production dashboard.

The important tradeoff is **trustworthy resolution per dollar**, not raw tokens or answer fluency. Cheap wrong answers are expensive when they send customers down the wrong operational path.

## Extension plan

Add harder holdout incidents (multiple simultaneous causes and misleading customer hypotheses), train/test separation, calibrated pairwise judging, prompt-injection fixtures, metrics by category and severity, confidence bounds, and a GitHub Actions offline test job. For production, add auth-scoped telemetry integrations and explicit escalation events with auditable approval rather than giving the agent unrestricted write access.

## References

- [OpenAI Agents SDK — tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK — token usage](https://openai.github.io/openai-agents-python/usage/)
- [OpenAI API pricing](https://platform.openai.com/docs/pricing)

MIT licensed. All identifiers, logs, organizations and incidents are synthetic.