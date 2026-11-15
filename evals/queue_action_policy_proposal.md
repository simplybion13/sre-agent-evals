# Queue-action policy adjudication (proposal, not applied)

## Observed ambiguity

The frozen 50-ticket development dataset has **two queue scenario templates**
with matching operational causes: all pool slots occupied, queue depth above
zero, and positive remaining org quota. Both require
`tune_concurrency`. One also requires `retry_with_backoff`, while the
other does not. The displayed ticket/customer context and mock telemetry do
not offer an independently testable discriminator to justify the difference.

In the measured v4 run, both models omitted `retry_with_backoff`
on T010, T020, T030, T040 and T050. The strict historical grader marked
all 10 model-ticket pairs unsolved, even though the primary diagnoses and
tune-concurrency action were correct.

## Proposed policy for human review

1. **Queue saturation with remaining organization quota:** prioritize
   reducing build fanout / tuning pool concurrency. A bounded backoff
   is **optional** when a safe retry is actionable; do not promise that
   repeated retries create more agent slots.
2. **Hard organization quota limit:** reduce in-flight runs or request a
   quota increase. Backoff alone cannot overcome the hard quota.
3. **Backend or regional capacity unavailable:** retry with exponential
   backoff and/or select a supported region/SKU. Backoff is appropriate here
   because host availability can fluctuate.
4. **Unidentified failure:** request the missing job ID; do not infer job
   success from a healthy pool status.

## Experimental integrity / next decision

**This document does not alter `data/tickets.jsonl`,
`scripts/generate_tickets.py`, `grade_labels`, or any historical result.**

Before making an action-policy v2, have a support SME adjudicate which
actions are mandatory, optional, or unsafe. Publish a separate versioned
dataset/rubric and compare under both old and new scoring; never
retroactively relabel v1–v4 published solve rates. The 15-ticket
challenge set deliberately avoids requiring backoff for saturated-queue
cases unless independently justified, and should be reported as its own
evaluation rather than merged into the historical 50-ticket series.
