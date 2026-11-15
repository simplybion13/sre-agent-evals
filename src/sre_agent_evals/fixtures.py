import json
from pathlib import Path
from .paths import DATA
from .schemas import Ticket

DOCS = {
    "images": "Supported build images: ubuntu-22.04, ubuntu-24.04, windows-2022. Image identifiers are exact and region-specific image availability may vary.",
    "skus": "Supported sizes: standard-2, standard-4, highmem-8. legacy-gpu and tiny-1 are not offered. Choose a supported SKU before retrying.",
    "quota": "Organization concurrency is a hard cap. Reduce concurrent jobs or request a quota increase; a retry does not override a quota limit.",
    "queue": "If queued_jobs exceeds available slots, reduce fanout or adjust pool concurrency. Inspect organization quota before attributing slow queue to load.",
    "capacity": "When backend capacity is unavailable, retry with exponential backoff or choose an alternate supported region/SKU. Include pool and job IDs in a support request if persistent.",
    "startup": "Bootstrap scripts must exit zero and reference installed binaries. Check agent startup logs, correct scripts, then retry a single job.",
    "authentication": "Agent registration requires a valid short-lived credential. Rotate expired credentials through your normal secret management workflow and retry; never paste keys into support tickets.",
}

def load_tickets(path: Path = DATA) -> list[Ticket]:
    tickets = [Ticket.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]
    if len({t.id for t in tickets}) != len(tickets):
        raise ValueError("Duplicate ticket IDs")
    return tickets


def lookup_fixture(ticket: Ticket, kind: str, key: str) -> dict:
    expected_id = {"pool": ticket.pool_id, "quota": ticket.org_id, "logs": ticket.job_id}[kind]
    if key != expected_id or expected_id is None:
        return {"error": "resource_not_found_or_access_denied"}
    return ticket.fixtures[kind]