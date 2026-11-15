"""Evidence-aware judge integration and conservative image/SKU audits (offline)."""
from sre_agent_evals.fixtures import load_tickets
from sre_agent_evals.judge import judge_payload
from sre_agent_evals.paths import JUDGE_RUBRICS
from sre_agent_evals.response_audit import audit_response
from sre_agent_evals.schemas import Diagnosis


def diagnosis(text, code="image_mismatch"):
    return Diagnosis(
        diagnosis_code=code,
        recommended_actions=["select_supported_image" if code == "image_mismatch" else "select_supported_sku"],
        evidence=["Failed job has an unsupported image or SKU."],
        customer_response=text,
    )


def test_experimental_v3_rubric_exists_and_historical_inputs_unchanged():
    assert all(path.exists() for path in JUDGE_RUBRICS.values())
    ticket = next(t for t in load_tickets() if t.category == "image")
    answer = diagnosis("Choose ubuntu-22.04.")
    calls = [{"name": "lookup_docs", "arguments": {"topic": "images"}}]
    v1 = judge_payload(ticket, answer, calls, rubric_version=1)
    v2 = judge_payload(ticket, answer, calls, rubric_version=2)
    v3 = judge_payload(ticket, answer, calls, rubric_version=3)
    assert "retrieved_documentation" not in v1
    assert "deterministic_advisory_audit" not in v1
    assert "deterministic_advisory_audit" not in v2
    assert isinstance(v1["answer"], str)
    assert v3["retrieved_documentation"] == v2["retrieved_documentation"]
    assert v3["retrieved_documentation"][0]["topic"] == "images"
    assert "ubuntu-22.04" in v3["retrieved_documentation"][0]["content"]
    assert v3["deterministic_advisory_audit"]["pass_advisory"] is True


def test_advisory_rejects_invented_image_without_flagging_reported_bad_image():
    unsupported = audit_response(diagnosis("Use ubuntu-99.99 to unblock the job."), [])
    assert {"code": "unsupported_image_recommendation", "values": ["ubuntu-99.99"]} in unsupported["findings"]
    existing = audit_response(
        diagnosis("The requested ubuntu-20.04 image is unsupported. Choose ubuntu-22.04."),
        [{"name": "lookup_docs", "arguments": {"topic": "images"}}],
    )
    assert existing["pass_advisory"]


def test_advisory_rejects_invented_sku_even_when_docs_were_called():
    bad = audit_response(
        diagnosis("Use ultra-gpu-999 instead; it's supported.", code="sku_unsupported"),
        [{"name": "lookup_docs", "arguments": {"topic": "skus"}}],
    )
    assert any(item["code"] == "unsupported_sku_recommendation" for item in bad["findings"])
    good = audit_response(
        diagnosis("Select standard-4 instead.", code="sku_unsupported"),
        [{"name": "lookup_docs", "arguments": {"topic": "skus"}}],
    )
    assert good["pass_advisory"]
