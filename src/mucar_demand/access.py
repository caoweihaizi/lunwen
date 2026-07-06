from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from mucar_sim.coverage import AccessAssignment
from .factorized import FactorizedOD


@dataclass(frozen=True)
class SatelliteAggregation:
    satellite_pairs_mbps: Mapping[Tuple[str, str], float]
    satellite_od_mbps: float
    local_delivery_mbps: float
    access_backlog_mbps: float


def aggregate_to_satellites(od: FactorizedOD, assignments: Sequence[AccessAssignment]):
    by_region = {assignment.region_id: assignment.selected_sat_id for assignment in assignments}
    if set(by_region) != set(od.region_ids) or len(by_region) != len(assignments):
        raise ValueError("access assignments must match OD regions exactly")
    categories = {region_id: by_region[region_id] for region_id in od.region_ids}
    groups = {}
    for index, region_id in enumerate(od.region_ids):
        groups.setdefault(categories[region_id], []).append(index)
    pairs, satellite_total = {}, 0.0
    local = backlog = 0.0
    for source, source_indices in groups.items():
        origin_sum = float(od.origin_factors[source_indices].sum())
        for destination, destination_indices in groups.items():
            destination_sum = float(od.destination_factors[destination_indices].sum())
            diagonal = 0.0
            if source == destination:
                diagonal = sum(od.origin_factors[i] * od.destination_factors[i] for i in source_indices)
            value = od.coefficient_mbps * (origin_sum * destination_sum - diagonal)
            if source is None or destination is None:
                backlog += value
            elif source == destination:
                local += value
            else:
                pairs[(source, destination)] = value
                satellite_total += value
    return SatelliteAggregation(dict(sorted(pairs.items())), satellite_total, local, backlog)
