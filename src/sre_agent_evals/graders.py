from .schemas import Diagnosis, Ticket

ALLOWED_DOC_TOPICS = {"images", "skus", "quota", "queue", "capacity", "startup", "authentication"}


def grade_tools(ticket: Ticket, calls: list[dict]) -> dict:
    """Deterministic required-call coverage and exact-ID / unnecessary-call checks."""
    expected = ticket.expected
    required = expected["required_tools"]
    required_pairs = {(item["name"], item["argument"]) for item in required}
    observed_pairs: set[tuple[str, str]] = set()
    violations: list[str] = []
    for c in calls:
        name, arguments = c.get("name"), c.get("arguments", {})
        if name == "lookup_docs":
            topic = arguments.get("topic", "")
            if topic not in ALLOWED_DOC_TOPICS:
                violations.append(f"invalid docs topic: {topic}")
            observed_pairs.add((name, topic))
        elif name in {"query_pool_status", "read_recent_job_logs", "check_quota"}:
            param, expected_id = {
                "query_pool_status": ("pool_id", ticket.pool_id),
                "read_recent_job_logs": ("job_id", ticket.job_id),
                "check_quota": ("org_id", ticket.org_id),
            }[name]
            actual = arguments.get(param)
            if actual != expected_id or expected_id is None:
                violations.append(f"wrong {param} for {name}: {actual}")
            observed_pairs.add((name, str(actual)))
        else:
            violations.append(f"unknown tool: {name}")
    missing = sorted(required_pairs - observed_pairs)
    if missing:
        violations.append(f"missing required calls: {missing}")
    # Overuse penalized: avoid a model brute forcing every endpoint.
    if len(calls) > len(required) + 2:
        violations.append(f"excessive calls: {len(calls)}")
    if ticket.job_id is None and any(c["name"] == "read_recent_job_logs" for c in calls):
        violations.append("logs queried despite missing job_id")
    return {"pass": not violations, "required_coverage": 1.0 if not required else len(required_pairs & observed_pairs) / len(required_pairs), "violations": violations}


def grade_labels(ticket: Ticket, output: Diagnosis | None) -> dict:
    if output is None:
        return {"diagnosis_correct": False, "actions_correct": False, "pass": False}
    target = ticket.expected
    diagnosis_correct = output.diagnosis_code == target["diagnosis"]
    actions_correct = set(target["required_actions"]).issubset(set(output.recommended_actions))
    # Required actions need not be ordered; a bad extra action is separately judged.
    return {"diagnosis_correct": diagnosis_correct, "actions_correct": actions_correct, "pass": diagnosis_correct and actions_correct}


def combined_solve(tool_grade: dict, label_grade: dict, judge_grade: dict | None = None) -> bool:
    return bool(tool_grade["pass"] and label_grade["pass"] and (judge_grade is None or judge_grade["pass"]))

def audit_queue_actions(ticket: Ticket, output: Diagnosis | None) -> dict:
    """Explain queue action labels without modifying the original strict grader.

    The frozen dataset has two saturated-queue templates with near-identical
    evidence, but only one requires retry_with_backoff as a secondary action.
    This report highlights secondary-action misses for human policy adjudication.
    """
    if ticket.category != "queue":
        return {"applicable": False}
    required = set(ticket.expected["required_actions"])
    observed = set(output.recommended_actions) if output is not None else set()
    secondary = "retry_with_backoff" in required
    return {
        "applicable": True,
        "primary_tune_concurrency_present": "tune_concurrency" in observed,
        "secondary_retry_required_by_label": secondary,
        "secondary_retry_present": "retry_with_backoff" in observed,
        "missing_required_actions": sorted(required - observed),
        "policy_review_candidate": bool(secondary and "retry_with_backoff" not in observed
                                        and "tune_concurrency" in observed),
        "note": "Advisory only; the frozen strict grade_labels / combined_solve are unchanged.",
    }
