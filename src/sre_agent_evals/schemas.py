from typing import Literal
from pydantic import BaseModel, Field

DiagnosisCode = Literal[
    "queue_saturation", "org_quota_exceeded", "image_mismatch", "sku_unsupported",
    "capacity_unavailable", "agent_bootstrap_failure", "agent_auth_failure",
    "healthy_or_transient", "insufficient_evidence",
]
# The SDK uses this Literal to expose a finite JSON Schema enum for lookup_docs.
# Keep it in sync with configs/tools/v2/tools.yaml; build_agent validates parity.
DocTopic = Literal[
    "images", "skus", "quota", "queue", "capacity", "startup", "authentication",
]

ActionCode = Literal[
    "tune_concurrency", "retry_with_backoff", "request_quota_increase",
    "select_supported_image", "select_supported_sku", "change_region_or_sku",
    "fix_bootstrap_script", "rotate_agent_credential", "collect_job_id",
    "monitor_and_recheck", "contact_support_with_ids",
]

class Diagnosis(BaseModel):
    diagnosis_code: DiagnosisCode
    recommended_actions: list[ActionCode] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    customer_response: str = Field(min_length=1)

class Ticket(BaseModel):
    id: str
    category: str
    variant: str
    message: str
    org_id: str
    pool_id: str
    job_id: str | None = None
    fixtures: dict
    expected: dict