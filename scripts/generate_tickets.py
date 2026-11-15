"""Deterministic, self-contained synthetic support incidents. No customer data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = [
    # category, diagnosis, actions, required tools: name + value reference (resolved below)
    ("queue", "queue_saturation", ["tune_concurrency"], [("query_pool_status", "pool"), ("check_quota", "org")]),
    ("quota", "org_quota_exceeded", ["request_quota_increase"], [("check_quota", "org"), ("query_pool_status", "pool"), ("lookup_docs", "quota")]),
    ("image", "image_mismatch", ["select_supported_image"], [("read_recent_job_logs", "job"), ("lookup_docs", "images")]),
    ("sku", "sku_unsupported", ["select_supported_sku"], [("read_recent_job_logs", "job"), ("lookup_docs", "skus")]),
    ("capacity", "capacity_unavailable", ["retry_with_backoff", "change_region_or_sku"], [("query_pool_status", "pool"), ("check_quota", "org"), ("lookup_docs", "capacity")]),
    ("startup", "agent_bootstrap_failure", ["fix_bootstrap_script"], [("read_recent_job_logs", "job"), ("query_pool_status", "pool"), ("lookup_docs", "startup")]),
    ("auth", "agent_auth_failure", ["rotate_agent_credential"], [("read_recent_job_logs", "job"), ("lookup_docs", "authentication")]),
    ("transient", "healthy_or_transient", ["monitor_and_recheck"], [("query_pool_status", "pool"), ("check_quota", "org")]),
    ("missing", "insufficient_evidence", ["collect_job_id"], [("query_pool_status", "pool")]),
    ("queue", "queue_saturation", ["tune_concurrency", "retry_with_backoff"], [("query_pool_status", "pool"), ("check_quota", "org")]),
]
INTRO = ["We're seeing", "Could you investigate", "Our team reports", "Since this morning, we're seeing", "Can support check"]
END = ["This blocks our PR pipeline.", "Our release is waiting.", "It started after a config change.", "Please advise before we retry.", "What should we do next?"]


def build():
    tickets = []
    for index in range(50):
        family, diagnosis, actions, requirements = TOPICS[index % 10]
        v = index // 10
        org = f"org-{100 + index}"
        pool = f"pool-{200 + index}"
        job = None if family == "missing" else f"job-{300 + index}"
        detail = {
            "queue": f"jobs waiting 18+ minutes in {pool} even though agents look alive",
            "quota": f"new parallel jobs sitting queued on {pool} after we raised our fanout",
            "image": f"an image resolution failure for {job} on {pool} using ubuntu-20.04",
            "sku": f"a runner provisioning failure for {job} requesting legacy-gpu",
            "capacity": f"provisioning pending for {pool} in region west-1 with standard-4",
            "startup": f"the runner for {job} exiting while its setup script runs",
            "auth": f"agent {job} stuck at registration with a forbidden response",
            "transient": f"a one-off queue spike on {pool} that may have cleared",
            "missing": f"an unexplained failure in {pool}; we don't have the job ID yet",
        }[family]
        message = f"{INTRO[v]} {detail}. Org: {org}; pool: {pool}" + (f"; job: {job}. " if job else ". ") + END[v]
        pool_data = {"pool_id": pool, "region": "west-1", "sku": "standard-4", "queued_jobs": 0,
                     "running_jobs": 2, "ready_agents": 6, "max_slots": 8, "capacity_state": "available", "agent_state": "healthy"}
        quota_data = {"org_id": org, "concurrency_limit": 30, "active_jobs": 6, "remaining": 24}
        logs_data = {"job_id": job, "events": ["runner allocated", "job completed or no recent errors"]}
        if family == "queue":
            pool_data.update(queued_jobs=24 + v * 3, running_jobs=8, ready_agents=8, max_slots=8)
            quota_data.update(active_jobs=8, remaining=22)
        elif family == "quota":
            pool_data.update(queued_jobs=15 + v, running_jobs=4, ready_agents=4, max_slots=8)
            quota_data.update(concurrency_limit=4, active_jobs=4, remaining=0)
        elif family == "image":
            logs_data["events"] = ["resolving image ubuntu-20.04", "ImageNotFound: ubuntu-20.04 is not supported"]
        elif family == "sku":
            logs_data["events"] = ["requesting legacy-gpu", "InvalidSku: legacy-gpu is not offered"]
        elif family == "capacity":
            pool_data.update(queued_jobs=12 + v, running_jobs=1, capacity_state="insufficient_backend_capacity", ready_agents=1)
            quota_data.update(active_jobs=1, remaining=29)
            logs_data["events"] = ["NoAvailableHost in west-1 for standard-4"]
        elif family == "startup":
            pool_data.update(agent_state="startup_failed", ready_agents=0)
            logs_data["events"] = ["bootstrap: line 12: buildkit: command not found", "bootstrap exited with status 127"]
        elif family == "auth":
            pool_data.update(agent_state="registering", ready_agents=0)
            logs_data["events"] = ["agent registration HTTP 401", "credential expired; token rejected"]
        elif family == "transient":
            pool_data.update(queued_jobs=0, running_jobs=2, ready_agents=6)
        elif family == "missing":
            logs_data = {"job_id": None, "events": []}
        mapping = {"pool": pool, "org": org, "job": job}
        expected = {"diagnosis": diagnosis, "required_actions": actions,
                    "required_tools": [{"name": name, "argument": mapping.get(arg, arg)} for name, arg in requirements]}
        tickets.append({"id": f"T{index+1:03}", "category": family, "variant": f"scenario-{v+1}",
                        "message": message, "org_id": org, "pool_id": pool, "job_id": job,
                        "fixtures": {"pool": pool_data, "quota": quota_data, "logs": logs_data},
                        "expected": expected})
    path = ROOT / "data" / "tickets.jsonl"
    path.write_text("".join(json.dumps(ticket) + "\n" for ticket in tickets))
    print(f"Wrote {len(tickets)} tickets to {path}")

if __name__ == "__main__":
    build()