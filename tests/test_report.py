from sre_agent_evals.eval_runner import estimate_cost, markdown_table, summarize


def test_cost_calculation():
    rates = {"models": {"mini": {"input_per_million": 1, "output_per_million": 2}}}
    assert estimate_cost("mini", 1_000_000, 1_000_000, rates) == 3
    assert estimate_cost("unknown", 42, 9, rates) is None


def test_summary_includes_failures_in_denominator():
    rows = [dict(model="mini", solved=s, latency_s=i + 1, input_tokens=100,
                 output_tokens=20, total_tokens=120, agent_cost_usd=0.01,
                 tool_grade={"pass": s}, label_grade={"diagnosis_correct": s}) for i, s in enumerate((True, False))]
    result = summarize(rows)
    assert result[0]["solve_rate_pct"] == 50.0
    assert "Avg $/ticket" in markdown_table(result)