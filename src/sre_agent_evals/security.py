"""Read-only, tenant-bound guard for synthetic tool IDs.

Never return data from an untrusted identifier unless it exactly matches the
ticket-scoped allowed identifier. Never interpolate a supplied ID into a query.
"""
import re

from .fixtures import lookup_fixture
from .schemas import Ticket

_ID_PATTERNS = {
    "pool": re.compile(r"pool-[0-9]+\Z"),
    "quota": re.compile(r"org-[0-9]+\Z"),
    "logs": re.compile(r"job-[0-9]+\Z"),
}
_ID_ATTRS = {"pool": "pool_id", "quota": "org_id", "logs": "job_id"}


def guarded_lookup(ticket: Ticket, kind: str, supplied_id: str) -> dict:
    """Fail closed for missing, malformed or wrong-tenant IDs before fixture access."""
    if kind not in _ID_PATTERNS:
        raise ValueError("Unsupported diagnostic resource kind")
    expected = getattr(ticket, _ID_ATTRS[kind])
    if (not isinstance(supplied_id, str)
            or not _ID_PATTERNS[kind].fullmatch(supplied_id)
            or expected is None
            or supplied_id != expected):
        return {"error": "resource_not_found_or_access_denied"}
    return lookup_fixture(ticket, kind, supplied_id)
