# Queue remediation labels — policy V2 (2026-11-15)

**Decision:** For queue saturation caused by a healthy pool with **all pool
slots allocated**, **available backend capacity**, and **remaining
organization concurrency quota**, require `tune_concurrency` as the
primary remediation. **Do not require `retry_with_backoff`** as a
second strict action. Retries may be helpful as optional client-side
load mitigation, but they do not create pool slots or eliminate the
underlying queue saturation. The included queue documentation says
to reduce fanout or adjust concurrency and to check quota, not to
prescribe retry backoff for this condition.

This is a **versioned evaluation-policy decision**, made after inspecting
the fixtures and canonical docs. It is *not* an independently validated
customer-support standard or an endorsement from a domain SME.

## Evidence-first rule, not special cases for five ticket IDs

The policy applies to **all tickets** meeting this predicate:

- Expected diagnosis is `queue_saturation` in the `queue` category.
- Pool agent state is `healthy` and backend capacity is `available`.
- `running_jobs == max_slots` and `ready_agents == max_slots`.
- `queued_jobs > 0`, and the organization has remaining concurrency quota.

This applies consistently to **T001, T010, T011, T020, T021, T030,
T031, T040, T041 and T050**. Their matching fixture conditions should
not produce two different mandatory-action rules based solely on the
ticket's numeric ID. The original label required `retry_with_backoff`
on five of them and omitted it on five others despite equivalent causes.

**Counterexample:** For backend capacity unavailability, the canonical
capacity documentation *does* recommend exponential backoff or changing
region/SKU. Keep the original `retry_with_backoff` requirement for
`capacity_unavailable` tickets. Do not weaken tool, diagnosis, judge or
other action requirements.

## Scoring decision and disclosure

| Model | Frozen label V1 strict solves | Offline V2-policy strict solves |
|---|---:|---:|
| GPT-6 Luna | **45/50 (90%)** | **50/50 (100%)** |
| GPT-6.1 Sol | **45/50 (90%)** | **50/50 (100%)** |

The V2 score is a **post-hoc reinterpretation of already-observed model
answers**, not an independent validation or an improvement in model
behavior. Both models previously failed the same five tickets solely
for the secondary backoff label. This does not establish production-level
reliability, and V2's perfect score must **never** replace the historical
90% headline. The proposed action policy should be externally reviewed
and tested on genuinely new tickets before adoption.

## Reproducibility and audit controls

The offline replay at `scripts/replay_queue_policy_v2.py` takes the
**original saved runs** and unchanged `data/tickets.jsonl`, reproduces
each row's V1 grades and strict solve status, then computes V2 strictly
using the predicate above. A V1 mismatch raises an error. It does not
edit labels, judge output, model responses, the original graders,
historical run files, or token/cost numbers.

```powershell
python scripts/replay_queue_policy_v2.py --runs results/current-model-50/runs.jsonl --dataset data/tickets.jsonl --output results/queue-policy-v2-replay.json
```

Review the saved replay report, which includes ticket-by-ticket old and
new grades. This requires **no API calls or API key**.

**Tradeoff acknowledged:** This rule tests whether recommended *primary
remediation* was correct under an evidence-grounded operational policy.
It does not prove that retry guidance is never appropriate, nor that the
existing 50 development tickets are representative. The next iteration
should use a separate human-reviewed dataset with cases where retry
backoff is necessary, optional, or actively harmful.
