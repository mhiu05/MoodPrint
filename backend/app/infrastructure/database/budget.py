"""Candidate connection budgets, including all processes and deployment generations.

Constants are planning assumptions, never a claim about current hosted role/pooler limits.
Tasks inside the API share its engine; only separate processes add separate pools.
"""

from __future__ import annotations

APPROVED_ROLE_LIMIT = 20
OBSERVED_ROLE_LIMIT = 10
RECOMMENDED_POOL_SIZE = 4
RECOMMENDED_POOL_OVERFLOW = 1
OVERLAP_PROCESSES = 2
MINIMUM_HEADROOM = 4
# Proactive worker pool (96 HD-02): DATABASE_POOL_SIZE=2, DATABASE_POOL_OVERFLOW=0.
WORKER_CONNECTIONS = 2
MAPS_CONNECTIONS = 1


def deployment_budget(*, api_pool=4, api_overflow=1, api_replicas=1,
                      proactive_connections=2, maps_connections=1, generations=2,
                      other_connections=0, operational_connections=1, emergency_reserve=3,
                      role_limit=20, pooler_limit=None) -> dict:
    values = (api_pool, api_overflow, api_replicas, proactive_connections, maps_connections,
              generations, other_connections, operational_connections, emergency_reserve, role_limit)
    if any(type(value) is not int or value < 0 for value in values) or min(api_pool, api_replicas, generations, role_limit) < 1:
        raise ValueError("Connection budgets require finite nonnegative integers and positive process counts")
    if pooler_limit is not None and (type(pooler_limit) is not int or pooler_limit < 1):
        raise ValueError("Invalid pooler limit")
    application = generations * ((api_pool + api_overflow) * api_replicas + proactive_connections + maps_connections) + other_connections
    required = application + operational_connections + emergency_reserve
    return {"application": application, "operational": operational_connections,
            "reserve": emergency_reserve, "required": required, "role_limit": role_limit,
            "pooler_limit": pooler_limit,
            "fits": required <= role_limit and (pooler_limit is None or application + operational_connections <= pooler_limit)}


def process_connections(pool_size: int, overflow: int) -> int:
    return pool_size + overflow


def overlapping_demand(
    pool_size: int,
    overflow: int,
    processes: int = OVERLAP_PROCESSES,
) -> int:
    return process_connections(pool_size, overflow) * processes


def headroom(
    pool_size: int,
    overflow: int,
    role_limit: int = APPROVED_ROLE_LIMIT,
    processes: int = OVERLAP_PROCESSES,
    worker_connections: int = WORKER_CONNECTIONS,
) -> int:
    return role_limit - overlapping_demand(pool_size, overflow, processes) - processes * (worker_connections + MAPS_CONNECTIONS)


def has_deployment_headroom(
    pool_size: int,
    overflow: int,
    role_limit: int = APPROVED_ROLE_LIMIT,
    processes: int = OVERLAP_PROCESSES,
    worker_connections: int = WORKER_CONNECTIONS,
) -> bool:
    return (
        headroom(pool_size, overflow, role_limit, processes, worker_connections)
        >= MINIMUM_HEADROOM
    )
