from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tickets.jsonl"
PRICING = ROOT / "configs" / "pricing.json"
RUBRIC = ROOT / "evals" / "judge_rubric.md"

DEFAULT_CONFIG_VERSION = 4
SUPPORTED_CONFIG_VERSIONS = (1, 2, 3, 4)
JUDGE_RUBRICS = {1: ROOT / 'evals' / 'judge_rubric.md', 2: ROOT / 'evals' / 'judge_rubric_v2.md'}


def config_paths(version: int = DEFAULT_CONFIG_VERSION) -> tuple[Path, Path]:
    """Return a matching versioned prompt and tool contract; never mix versions."""
    if version not in SUPPORTED_CONFIG_VERSIONS:
        raise ValueError(f"Unsupported agent config version: {version}")
    return (
        ROOT / "configs" / "prompts" / f"v{version}" / "system.md",
        ROOT / "configs" / "tools" / f"v{version}" / "tools.yaml",
    )


PROMPT, TOOLS = config_paths()
