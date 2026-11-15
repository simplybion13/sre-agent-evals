"""New-model price setup is opt-in and does not change historical rates."""
import json

from sre_agent_evals.eval_runner import estimate_cost
from sre_agent_evals.paths import PRICING


def test_current_model_prices_are_positive_and_historical_models_preserved():
    cfg = json.loads(PRICING.read_text(encoding="utf-8"))
    models = cfg["models"]
    assert {"gpt-4.1-mini", "gpt-4.1", "gpt-6-luna", "gpt-6.1-sol"} <= set(models)
    assert models["gpt-4.1-mini"] == {"input_per_million": 0.4, "output_per_million": 1.6}
    assert models["gpt-4.1"] == {"input_per_million": 2.0, "output_per_million": 8.0}
    assert models["gpt-6-luna"] == {"input_per_million": 0.10, "output_per_million": 0.50}
    assert models["gpt-6.1-sol"] == {"input_per_million": 2.0, "output_per_million": 10.0}
    for name in models:
        assert all(rate > 0 for rate in models[name].values())


def test_cost_uses_token_usage_not_a_fixed_model_multiplier():
    prices = json.loads(PRICING.read_text(encoding="utf-8"))
    assert abs(estimate_cost("gpt-6-luna", 1000, 100, prices) - 0.00015) < 1e-12
    assert abs(estimate_cost("gpt-6.1-sol", 1000, 100, prices) - 0.003) < 1e-12
