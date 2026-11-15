# Architecture and evaluation decision log — interview brief

**Project:** Synthetic CI/CD build-pool support agent. Built rapidly with AI
coding assistance; the relevant ownership is experimental design, architecture
tradeoffs, diagnosis of measured failures, security boundaries, and honest
interpretation. The pace of commits is not evidence of engineering maturity.

## The product question

Can a **lower-cost model** solve customer support incidents reliably if we
design the surrounding agent system well enough, instead of paying for a
stronger model on every ticket?

Customer-facing target metrics are **cost per safely resolved incident**,
diagnosis and remediation correctness, escalation rate, response latency,
and harmful-error severity. Our benchmark currently captures only a
synthetic subset; per-ticket candidate inference prices do **not** include
controller infrastructure, real diagnostic-tool time/cost, LLM judge cost,
or impact of misdiagnosis.

## Decision 1 — Why GPT-4.1 and GPT-4.1-mini initially?

The controlled pair uses two model sizes in the same generation. GPT-4.1
was the higher-cost quality reference; GPT-4.1-mini was the cost-sensitive
candidate. The point was not that they were the latest models indefinitely,
but to test reliability versus inference economics on the **same frozen**
ticket set, rubric and recorded tool behavior.

On 50 development tickets in v2, mini solved 35/50 (70%); GPT-4.1 solved
45/50 (90%). The gap made it useful to ask whether orchestration could
narrow the difference.

## Decision 2 — Why V3 regressed instead of improving

V3 added prompt constraints, strict ID guarding and extra guidance, but
the measured strict solve rate **fell** to 33/50 (66%) mini and 41/50
(82%) GPT-4.1. Failure inspection showed the mini repeatedly failed
required quota-doc retrieval and missing-job-ID reasoning. GPT-4.1 had
queue backoff omissions and some unnecessary/missing tool reads.

**Interpretation:** More instructions did not reliably control procedural
tool selection. The exact causal decomposition remains uncertain because
runs were stochastic, ticket variants were synthetic, and improvements
were made against the development set. We kept V3 as a visible negative
result instead of rewriting history.

## Decision 3 — Why deterministic V4 orchestration

V4 moved read-only evidence collection into observable controller logic
bounded by ticket-scoped identifiers and fixture observations. The model
receives a sourced evidence bundle and produces structured diagnosis and
customer prose. The controller never consults expected diagnosis/action
labels while selecting reads.

This trades model autonomy for predictability and traceability, with costs:
the controller becomes part of the product, mock reads lack real network
latency, and 100% tool-grade compliance is a **controller-level** result,
not a claim about independent model tool use.

On the same synthetic development set, both models solved 44/50 (88%),
and mini's estimated candidate inference spend fell to $0.000615/attempt
from $0.001577 in V2. The measured **system** improved; the underlying
model weights were unchanged. V4 recorded 0/100 safety-gate corrections.

## Decision 4 — Why deterministic graders plus a separate LLM judge

Strict code graders check tool names/IDs, expected diagnosis and required
actions. The LLM judge assesses customer-facing clarity, grounding and
safety. These answer different questions and should not be combined into
a single fluent-model opinion.

In repeated adversarial testing, GPT-4.1's A009 candidate had a supported
image recommendation with recorded image-doc retrieval, but historical
judge v1 marked it insufficiently grounded on the first run. A separate
judge-v3 replay gave the unchanged saved answer 8/8 (versus original 6/8).
The historical failure was **not** rewritten. Judge v2 also disagreed with
human-authored expectations on 1–2 of six calibration cases across runs;
judge v3 matched 6/6 in one run. Six examples cannot validate a judge.

The lesson: evaluation design and calibration are part of product quality;
do not optimize the agent to a miscalibrated judge. Keep the original rubric
for historical comparisons and report later rubric studies separately.

## Decision 5 — Why validate with current models now

GPT-4.1 was a reasonable controlled historical pair, but a November 2026
OpenAI interview should demonstrate awareness of **current** model choices.
Use **GPT-6 Luna** (economical) and **GPT-6.1 Sol** (stronger reference)
with **the same frozen V4 configuration** on a 5-ticket smoke test first.
If the API/SDK supports both IDs and the smoke is clean, run the identical
50-ticket development dataset, historical judge rubric v1, with model names
and prices recorded. Follow with the pre-existing challenge and adversarial
sets as separate exploratory evaluations. Do **not** edit earlier V1–V4
scores, labels or prompts to make either new model look better.

Only compare candidate costs on the same pricing tier, window and usage
definition. Current listed **standard short-context** token rates:
`gpt-6-luna` $0.10/M input and $0.50/M output;
`gpt-6.1-sol` $2/M input and $10/M output (checked 2026-11-15).
Actual invoices may differ for cached input, tier, reasoning tokens and
other charges. Verify availability in the account and SDK before treating
the run as completed.

## Limitations and next decision

- Synthetic incident templates are highly related and were studied
  iteratively. A challenge suite written after seeing failure patterns
  is not a genuine unseen customer distribution.
- One run per model/configuration on the original 50 is not a reliable
  estimate of a performance difference. Repeated ten-case adversarial
  attempts re-use the same tickets.
- Queue secondary-action labels are inconsistent across some otherwise
  similar variants; SME adjudication should precede rescore.
- Real operation would require tenant isolation, production-read budget,
  human escalation policy, error-severity handling and end-to-end cost.
- No claim is made that this synthetic prototype is production-ready.

**What I would do differently next:** recruit an independent domain reviewer,
collect genuinely unseen real incident patterns (sanitized and consented),
calibrate the judge blindly, and test **fully loaded cost per safely resolved
incident**, not just API token price or a single strict solve metric.

**AI assistance disclosure:** AI coding tools accelerated implementation
and iteration. The meaningful evidence of ownership is the ability to
explain each architectural decision, rerun each experiment, identify
confounders, and change the plan when results contradict the hypothesis.
Do not imply all code was handwritten.
