"""Pool budget for the moodprint_backend role.

One API process uses 5 connections plus 2 overflow (7). A deployment may run
two processes at once, which is 14 connections. The approved role limit is 20,
leaving headroom for Supavisor and short operational sessions. The previous
code default of 8+4 does not fit the observed role limit of 10, and 5+5 leaves
no headroom once two processes overlap.
"""

from __future__ import annotations

APPROVED_ROLE_LIMIT = 20
OBSERVED_ROLE_LIMIT = 10
RECOMMENDED_POOL_SIZE = 5
RECOMMENDED_POOL_OVERFLOW = 2
OVERLAP_PROCESSES = 2
MINIMUM_HEADROOM = 4


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
) -> int:
    return role_limit - overlapping_demand(pool_size, overflow, processes)


def has_deployment_headroom(
    pool_size: int,
    overflow: int,
    role_limit: int = APPROVED_ROLE_LIMIT,
    processes: int = OVERLAP_PROCESSES,
) -> bool:
    return headroom(pool_size, overflow, role_limit, processes) >= MINIMUM_HEADROOM
