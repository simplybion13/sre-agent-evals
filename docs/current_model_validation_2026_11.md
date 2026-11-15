# Current-model validation: GPT-6 Luna versus GPT-6.1 Sol

**Run date:** 2026-11-15 (UTC). **Status:** completed, exploratory synthetic development benchmark.

## Question and controlled setup

Does a cost-efficient current model deliver comparable strict outcomes to a
higher-priced model under the V4 **controller-led, read-only evidence collection**
architecture? Both models ran the same 50 pre-existing synthetic development
tickets under V4 system instructions, tool contract, frozen labels and strict
graders, with **LLM judge GPT-4.1, rubric version 1**. **The judge model and rubric were intentionally fixed across historical and current candidate evaluations to avoid confounding model changes with judge changes.** Each model attempted every
ticket once, sequentially. These are **system-level** results: V4 tool calls
were selected by the controller rather than chosen by the LLM.

The first five-ticket smoke test passed 5/5 for both candidates. The full
50-ticket run was separately executed and is the basis for the table below.
The result figures were supplied from the local runner's `report.md`,
`summary.csv`, and 100-row `runs.jsonl` on 2026-11-15; no independently
repeated 50-ticket run or production validation is claimed here.

## Full 50-ticket results

| Metric | GPT-6 Luna (`gpt-6-luna`) | GPT-6.1 Sol (`gpt-6.1-sol`) |
|---|---:|---:|
| Strict solves | **45/50 (90%)** | **45/50 (90%)** |
| Correct primary diagnosis | 50/50 (100%) | 50/50 (100%) |
| Required-tool grade | 50/50 (100%) | 50/50 (100%) |
| LLM judge pass | 50/50 (100%) | 50/50 (100%) |
| API / judge errors | 0 / 0 | 0 / 0 |
| Safety-controller corrections | 0 | 0 |
| Mean agent latency | 4.02 s | 4.21 s |
| P95 agent latency | 5.72 s | 5.42 s |
| Mean input / output tokens | 928 / 265 | 928 / 206 |
| Estimated candidate inference / attempted ticket | **$0.000225** | **$0.003915** |
| Estimated candidate inference / strict solve | **$0.000250** | **$0.004350** |

At the illustrative listed standard-tier prices, **Luna's estimated candidate
inference cost per attempt was about 94.3% lower**, while the models had the
same observed strict solve rate. The cost-per-solve numbers divide mean
attempt cost by measured solve fraction and are **not total operating cost**.
These estimates exclude the judge, real diagnostic tool calls, controller
infrastructure, escalation and failure severity. Input caching, billing
tier, reasoning usage and other account-specific charges may differ from
the illustrative pricing model. Latency covers the agent portion, not a
real distributed support workflow.

## What failed and why it matters

Each model failed the **same five tickets**: `T010`, `T020`, `T030`,
`T040`, and `T050`, all `queue_saturation` cases. Across those ten
attempts, the primary diagnosis and V4 tool grade were correct and the
separate answer-quality judge passed. The strict action grade failed
because `retry_with_backoff` was required by the frozen label but was
not included in the recommended action list. The models did recommend
`tune_concurrency`; some also recommended monitoring or managing load.

The runner's advisory `queue_action_audit` flagged these as
policy-review candidates. Comparing **all ten** `queue_saturation`
fixtures and the canonical `queue` documentation confirms that the
five failures and five passes describe the same operational condition:
healthy agents, available backend capacity, occupied pool slots and
unused organization quota. Only the original frozen label's secondary
action differs across these equivalent scenarios.

The resulting [queue remediation policy V2](queue_action_policy_v2.md)
requires `tune_concurrency` for this condition, while treating
`retry_with_backoff` as optional. This is a **documented owner judgment
based on fixture evidence and customer impact**, not a change in model
behavior. Regrading the **unchanged saved outputs offline** under that
versioned policy produces **50/50 (100%) for both models**. This is a
**post-hoc policy-rescore**, not a new benchmark or independent evidence
of perfect generalization. The original **45/50 (90%)** strict scores
remain the official frozen-label results. An independent SME review
should assess the revised rule before operational adoption.

## Historical context (do not combine these as a new controlled trial)

| Configuration and model | Strict solves | Estimated candidate inference / ticket |
|---|---:|---:|
| V4 GPT-4.1-mini (historical run) | 44/50 (88%) | $0.000615 |
| V4 GPT-4.1 (historical run) | 44/50 (88%) | $0.003231 |
| V4 GPT-6 Luna (this run) | 45/50 (90%) | $0.000225 |
| V4 GPT-6.1 Sol (this run) | 45/50 (90%) | $0.003915 |

The single-ticket difference between model generations is not evidence of
statistical superiority. The historical and modern runs occurred at
different times; this is a descriptive comparison across runs, not an
independent randomized production experiment. V4 controlled evidence
collection is a major contributor to every model's required-tool grade.

## Product interpretation and next gate

The narrow, supported observation is that **the economical current model
matched the stronger current model on these 50 synthetic tickets at much
lower estimated candidate inference spend**. The original product
hypothesis remains plausible: reliability per dollar is often determined
by *system design*, not model size alone. It has **not** been demonstrated
for real customers, unseen incident distributions, or total cost to serve.

Before an actual deployment decision: independently validate the
owner-defined V2 queue policy, measure repeated-run uncertainty, test genuinely unseen
tickets, include diagnostic network time/cost and judge/escalation burden,
evaluate severity-weighted misdiagnoses, and define human handoff. Avoid
more prompt tuning against these already-studied 50 tickets.

**Reproduce (requires your own API key; never commit credentials):**

```powershell
sre-eval --models gpt-6-luna gpt-6.1-sol --config-version 4 --judge-rubric-version 1 --limit 5 --output results/current-model-smoke
sre-eval --models gpt-6-luna gpt-6.1-sol --config-version 4 --judge-rubric-version 1 --output results/current-model-50
```

Price inputs: `configs/pricing.json`, checked 2026-11-15.
Original row-level outputs should be retained with the local benchmark
artifacts; this document contains aggregate findings and failure IDs, not
raw API response transcripts.
