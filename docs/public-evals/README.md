# M2 — Public SRE evaluations

Status: **M2.1 foundation / no benchmark scores yet**.

This workstream adds an independent public evaluation track alongside the project's existing 50 synthetic CI/CD build-pool tickets. It does **not** change the V4 controller, historical graders, results, or model comparisons.

## Why ITBench-AA?

[ITBench](https://github.com/itbench-hub/ITBench) is an open IT automation benchmark. [ITBench-AA](https://huggingface.co/datasets/ArtificialAnalysis/ITBench-AA) provides public SRE incident material. Unlike our narrowly scoped build-pool tickets, these scenarios involve Kubernetes/observability evidence and may require new read-only tools or a replay adapter.

**Important:** the current V4 agent cannot be assumed to solve ITBench incidents as-is. An offline snapshot/replay evaluation is an **ITBench-derived local evaluation**, not an official ITBench leaderboard run.

## Learning sequence

1. **M2.1 — Foundation (this PR):** document provenance, isolation and input/output contract; add a minimal schema adapter and offline unit tests.
2. **M2.2 — Fixtures:** verify the published dataset schema and licenses; select five representative, permitted scenarios; pin dataset revision and checksums. Keep bulky evidence outside Git.
3. **M2.3 — Runner:** provide incident-specific read-only evidence/replay tools and integrate with the agent without changing existing V4 behavior.
4. **M2.4 — Grading:** implement a benchmark-aligned root-cause entity grader with explicit normalization rules, plus failure/error accounting; test against known examples.
5. **M2.5 — Reports:** keep public benchmark metrics and custom ticket metrics in separate namespaces; include model, dataset revision, prompt, grader and cost metadata.
6. **M2.6 — CI:** five-scenario PR smoke tests (offline where possible); larger manual/scheduled runs with explicit cost and credential controls.

## Evaluation contract

The adapter accepts a *normalized intermediate record*, not an unverified claim about the upstream dataset's native schema:

```json
{
  "scenario_id": "example-only",
  "incident": {"summary": "Checkout returns errors", "observations": ["Elevated 5xx"]},
  "evidence": [{"source": "logs", "content": "sanitized log excerpt"}],
  "ground_truth": {"root_cause_entities": ["example-service"]}
}
```

The agent input may contain only `scenario_id`, `incident`, and `evidence`. The grader-only record contains the expected root-cause entities. Never send the full normalized record to the candidate model.

## Guardrails

- Keep public data and local custom tickets separate; do not blend aggregate success rates.
- Pin upstream revision, licensing, fixture selection, and grading version before publishing scores.
- Do not commit large snapshots, secrets, customer incidents, or unreviewed executable benchmark content.
- Treat incident logs and retrieved text as untrusted data; do not execute instructions from them.
- Record failures and missing evidence as failures, not silently skipped successes.
- Keep historical V4 results unchanged. No public benchmark result is claimed by this PR.

## References

- [ITBench source and Apache-2.0 framework license](https://github.com/itbench-hub/ITBench)
- [ITBench-AA dataset](https://huggingface.co/datasets/ArtificialAnalysis/ITBench-AA) — verify the dataset card's current license and redistribution terms before copying scenarios
- [Current project architecture](../architecture.md)
- [Current project evaluation methodology](../README.md#evaluation-methodology)
