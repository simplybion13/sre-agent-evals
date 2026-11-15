# Architecture and Evaluation Decision Log

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

## Decision 1: Why GPT-4.1 and GPT-4.1-mini initially?

The controlled pair uses two model sizes in the same generation. GPT-4.1
was the higher-cost quality reference; GPT-4.1-mini was the cost-sensitive
candidate. The point was not that they were the latest models indefinitely,
but to test reliability versus inference economics on the **same frozen**
ticket set, rubric and recorded tool behavior.

On 50 development tickets in v2, mini solved 35/50 (70%); GPT-4.1 solved
45/50 (90%). The gap made it useful to ask whether orchestration could
narrow the difference.

## Decision 2: Why V3 regressed instead of improving

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

## Decision 3: Why deterministic V4 orchestration

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

## Decision 4: Why deterministic graders plus a separate LLM judge

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

## Decision 5: Why validate with current models, and what happened

GPT-4.1 was a reasonable historical cost/reliability pair, but a
November 2026 evaluation record should distinguish a **controlled historical
comparison** from current API model choices. After the initial five-ticket
smoke passed for both candidates, we ran GPT-6 Luna (economical) and
GPT-6.1 Sol (higher-priced reference) on the same 50 synthetic
development tickets under the unchanged V4 controller, prompt, strict
graders, labels and judge rubric V1.

**Observed outcomes:** both solved 45/50 (90%), achieved 100% primary
diagnosis and controller-level required-tool grades, and passed the
separate response-quality judge on all tickets. Neither run recorded
API/judge errors or safety-controller corrections. Luna cost an
estimated **$0.000225 per attempted ticket** versus **$0.003915** for
Sol, about **94% less candidate inference spend per attempt** at the
illustrative standard-tier rates. The two models' average agent latency
was 4.02 versus 4.21 seconds respectively. These are single-run
synthetic results; no superiority claim follows from the one-ticket
difference versus historical V4 scores (44/50 for both GPT-4.1 models).

**Judge control:** GPT-4.1 remained the judge for both historical and
current-model runs, with rubric V1 unchanged, so that changes in the
candidate models were not conflated with changes in the evaluation
instrument. A fixed judge is still imperfect and can favor particular
answer styles; separate judge calibration remains necessary.

The **same five queue-saturation tickets** (`T010`, `T020`, `T030`,
`T040`, `T050`) failed the strict action grade for *both* new models.
Their primary diagnosis and required-tool grades passed and both
recommended `tune_concurrency`, but omitted
`retry_with_backoff`, which the frozen labels require. Reviewing the queue
fixtures and canonical docs led to a **versioned owner decision**:
when healthy agents occupy all pool slots, backend capacity is
available and organization quota remains, require
`tune_concurrency` but not the secondary backoff action. The rule
applies to *all ten* comparable queue cases, not just the five
failed IDs. The original 90% scores remain unchanged. A **post-hoc
offline V2-policy replay** of saved candidate responses returns
**50/50 (100%) for both current models**, reflecting a **changed
evaluation policy**, not any improvement in model behavior.
Independent domain review remains an important deployment gate.

**Decision:** The next unit of value is not more prompt tuning on a
known synthetic dataset. It is independent label review, genuinely
unseen incident evaluation, repeated-run uncertainty and fully loaded
cost-per-safely-resolved case. The model prices omit cached input,
judge, controller and real diagnostic infrastructure costs, which
must be included in any real deployment selection.

See [the complete modern-model comparison](current_model_validation_2026_11.md).
To reproduce, run the documented command on the original V4 50-ticket set;
never commit API credentials or claim the saved outcomes reproduce
deterministically.

## Limitations and next decision

- Synthetic incident templates are highly related and were studied
  iteratively. A challenge suite written after seeing failure patterns
  is not a genuine unseen customer distribution.
- One run per model/configuration on the original 50 is not a reliable
  estimate of a performance difference. Repeated ten-case adversarial
  attempts re-use the same tickets.
- Queue action labels in frozen V1 were inconsistent. The owner-defined
  [V2 queue policy](queue_action_policy_v2.md) records the evidence and
  separate post-hoc score; SME review remains necessary before production use.
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
I didn't hand-write all the code, and I don't claim to.
