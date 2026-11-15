from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tickets.jsonl"
PROMPT = ROOT / "configs" / "prompts" / "v1" / "system.md"
TOOLS = ROOT / "configs" / "tools" / "v1" / "tools.yaml"
PRICING = ROOT / "configs" / "pricing.json"
RUBRIC = ROOT / "evals" / "judge_rubric.md"