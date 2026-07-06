import hashlib
import json
import math
from typing import Mapping, Sequence

import numpy as np

from mucar_data.contracts import SimulationContract
from .constellation import build_walker_constellation
from .coordinates import gmst_degrees, julian_date_utc
from .coverage import GroundRegion, assign_access
from .orbit import propagate
from .topology import build_operational_topology, build_planned_topology


def _audit_times(period_s: float, step_s: int):
    stop = int(math.ceil(period_s))
    times = list(range(0, stop + 1, step_s))
    if not times or times[-1] != stop:
        times.append(stop)
    return tuple(times)


def canonical_audit_hash(audit: Mapping[str, object]) -> str:
    payload = json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def summarize_access_history(assignments, durations_s):
    if len(assignments) != len(durations_s) or not assignments:
        raise ValueError("assignments and durations must be non-empty and aligned")
    visible = []
    uncovered_steps = current_uncovered = maximum_uncovered = 0
    handovers = reattachments = 0
    previous_sat = None
    previously_covered = False
    ever_covered = False
    for assignment, duration in zip(assignments, durations_s):
        if duration < 0:
            raise ValueError("durations must be nonnegative")
        visible.append(assignment.visible_count)
        if assignment.access_backlog:
            uncovered_steps += 1
            current_uncovered += duration
            maximum_uncovered = max(maximum_uncovered, current_uncovered)
            previously_covered = False
            continue
        current_uncovered = 0
        if previously_covered and assignment.selected_sat_id != previous_sat:
            handovers += 1
        elif ever_covered and not previously_covered:
            reattachments += 1
        previous_sat = assignment.selected_sat_id
        previously_covered = True
        ever_covered = True
    return {
        "min_visible_count": min(visible), "mean_visible_count": sum(visible) / len(visible),
        "max_visible_count": max(visible), "uncovered_step_count": uncovered_steps,
        "max_uncovered_duration_s": maximum_uncovered, "handover_count": handovers,
        "reattachment_count": reattachments,
    }


def audit_one_orbit(contract: SimulationContract, regions: Sequence[GroundRegion]):
    satellites = build_walker_constellation(contract)
    times = _audit_times(contract.orbit_period_s, contract.time.orbit_update_s)
    region_histories = {region.region_id: [] for region in regions}
    durations = []
    errors = []
    maximum_radius_error = 0.0
    directed_counts, undirected_counts, degrees, distances = [], [], [], []
    for time_index, time_s in enumerate(times):
        positions = propagate(contract, satellites, time_s)
        radius_error = np.max(np.abs(np.linalg.norm(positions.eci_km, axis=1) - contract.orbit_radius_km))
        maximum_radius_error = max(maximum_radius_error, float(radius_error))
        planned = build_planned_topology(contract, positions, satellites)
        operational = build_operational_topology(planned, set())
        if operational != planned:
            errors.append(f"operational topology differs without failures at {time_s}")
        directed_counts.append(len(planned.directed_links))
        undirected_counts.append(len(planned.directed_links) // 2)
        degree = {node: 0 for node in planned.nodes}
        reverse = {(link.src, link.dst): link for link in planned.directed_links}
        for link in planned.directed_links:
            degree[link.src] += 1
            distances.append(link.distance_km)
            other = reverse.get((link.dst, link.src))
            if other is None or other.distance_km != link.distance_km:
                errors.append(f"asymmetric link at {time_s}: {link.src}->{link.dst}")
        degrees.extend(degree.values())
        assignments = assign_access(contract, positions, regions)
        duration = times[time_index + 1] - time_s if time_index + 1 < len(times) else 0
        durations.append(duration)
        for assignment in assignments:
            region_histories[assignment.region_id].append(assignment)
    if maximum_radius_error > 1e-9:
        errors.append(f"maximum ECI radius error exceeds tolerance: {maximum_radius_error}")
    if degrees and max(degrees) > contract.isl.intra_plane_neighbors + contract.isl.inter_plane_neighbors_max:
        errors.append(f"maximum node degree exceeds contract: {max(degrees)}")
    region_report = []
    for region_id in sorted(region_histories):
        region_report.append({"region_id": region_id, **summarize_access_history(region_histories[region_id], durations)})
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": [],
        "contract_sha256": contract.config_sha256,
        "epoch_utc": contract.time.epoch_utc,
        "julian_date_epoch": julian_date_utc(contract.time.epoch_utc),
        "gmst_epoch_deg": gmst_degrees(contract.time.epoch_utc),
        "orbit_period_s": contract.orbit_period_s,
        "orbit_update_s": contract.time.orbit_update_s,
        "snapshot_count": len(times),
        "first_time_s": times[0],
        "last_time_s": times[-1],
        "satellite_count": len(satellites),
        "region_count": len(regions),
        "maximum_eci_radius_error_km": maximum_radius_error,
        "planned_directed_link_count": {"min": min(directed_counts), "max": max(directed_counts)},
        "planned_undirected_link_count": {"min": min(undirected_counts), "max": max(undirected_counts)},
        "node_degree": {"min": min(degrees), "max": max(degrees)},
        "link_distance_km": {"min": min(distances), "max": max(distances)},
        "regions": region_report,
    }
