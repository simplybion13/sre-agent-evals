from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.graders import combined_solve, grade_labels, grade_tools
from sre_agent_evals.schemas import Diagnosis


def test_correct_tools_pass_and_wrong_org_fails():
    ticket = load_tickets()[1]
    calls = []
    for needed in ticket.expected["required_tools"]:
        field = {"check_quota": "org_id", "query_pool_status": "pool_id", "lookup_docs": "topic"}[needed["name"]]
        calls.append({"name": needed["name"], "arguments": {field: needed["argument"]}})
    assert grade_tools(ticket, calls)["pass"]
    bad = [dict(x) for x in calls]
    bad[0] = {"name": "check_quota", "arguments": {"org_id": "someone-else"}}
    assert not grade_tools(ticket, bad)["pass"]


def test_missing_job_is_not_queried():
    ticket = next(x for x in load_tickets() if x.category == "missing")
    assert not grade_tools(ticket, [{"name": "read_recent_job_logs", "arguments": {"job_id": "made-up"}}])["pass"]


def test_labels_are_independent_of_tools():
    ticket = load_tickets()[0]
    output = Diagnosis(diagnosis_code="queue_saturation", recommended_actions=["tune_concurrency"], evidence=["8/8 occupied"], customer_response="Reduce fanout")
    assert grade_labels(ticket, output)["pass"]
    assert not combined_solve({"pass": False}, grade_labels(ticket, output))
    assert not grade_labels(ticket, None)["pass"]