import hashlib
import json
from typing import Mapping

from mucar_data.contracts import ResearchContract, SimulationContract
from mucar_sim.constellation import build_walker_constellation
from mucar_sim.coverage import GroundRegion, assign_access
from mucar_sim.orbit import propagate
from .access import aggregate_to_satellites
from .config import DemandContract
from .factorized import FactorizedOD
from .interventions import apply_intervention, choose_hotspots
from .spatial import DemandRegion, spatial_weights
from .temporal import simulation_datetime


def canonical_demand_hash(audit: Mapping[str, object]):
    payload = json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sample_indices(research: ResearchContract):
    indices = []
    for name in ("train", "validation", "calibration", "test"):
        split = research.splits[name]
        indices.extend((split.start, (split.start + split.stop - 1) // 2, split.stop - 1))
    return tuple(indices)


def audit_demand_pipeline(demand: DemandContract, research: ResearchContract, simulation: SimulationContract, temporal_slots, regions):
    errors = []
    if len(temporal_slots) != demand.expected_temporal_slots:
        errors.append(f"expected {demand.expected_temporal_slots} temporal slots, found {len(temporal_slots)}")
    if len(regions) != demand.expected_regions:
        errors.append(f"expected {demand.expected_regions} regions, found {len(regions)}")
    if temporal_slots and (temporal_slots[0].timestamp_index != 0 or temporal_slots[-1].timestamp_index != len(temporal_slots) - 1):
        errors.append("temporal slot indices are not complete")
    satellites = build_walker_constellation(simulation)
    ground_regions = tuple(GroundRegion(region.region_id, region.centroid_lat, region.centroid_lon) for region in regions)
    region_ids = tuple(region.region_id for region in regions)
    scenario_hotspots = {
        name: choose_hotspots(regions, scenario, simulation.seeds.development, simulation.seeds)
        for name, scenario in demand.scenarios.items()
    }
    records = []
    for sample_number, slot_index in enumerate(_sample_indices(research)):
        slot = temporal_slots[slot_index]
        current_simulation_time = simulation_datetime(simulation, slot_index)
        weights = spatial_weights(regions, current_simulation_time, demand)
        base = FactorizedOD.from_weights(slot.total_demand_mbps, region_ids, weights, weights)
        positions = propagate(simulation, satellites, slot_index * simulation.traffic_interval_s)
        assignments = assign_access(simulation, positions, ground_regions)
        for name, scenario in demand.scenarios.items():
            if scenario.duration_slots <= 1:
                relative_slot = 0
            else:
                positions_to_audit = (0, scenario.duration_slots // 2, scenario.duration_slots - 1)
                relative_slot = positions_to_audit[sample_number % 3]
            changed, metadata = apply_intervention(base, scenario, scenario_hotspots[name], relative_slot)
            aggregation = aggregate_to_satellites(changed, assignments)
            reconstructed = aggregation.satellite_od_mbps + aggregation.local_delivery_mbps + aggregation.access_backlog_mbps
            tolerance = max(demand.conservation_abs_tolerance_mbps, changed.total_mbps * demand.conservation_rel_tolerance)
            error = abs(reconstructed - changed.total_mbps)
            if error > tolerance:
                errors.append(f"conservation failed at slot {slot_index} scenario {name}: {error}")
            records.append({
                "time_slot": slot_index, "partition": next(key for key, split in research.splits.items() if split.start <= slot_index < split.stop),
                "source_timestamp": slot.timestamp,
                "simulation_timestamp_utc": current_simulation_time.isoformat().replace("+00:00", "Z"),
                "scenario": name, "relative_slot": relative_slot,
                "base_total_mbps": metadata["base_total_mbps"], "scenario_total_mbps": metadata["scenario_total_mbps"],
                "mapped_satellite_od_mbps": aggregation.satellite_od_mbps,
                "local_delivery_mbps": aggregation.local_delivery_mbps,
                "access_backlog_mbps": aggregation.access_backlog_mbps,
                "conservation_error_mbps": error, "spatial_weight_sum": float(weights.sum()),
            })
    return {
        "status": "PASS" if not errors else "FAIL", "errors": errors, "warnings": [],
        "temporal_slot_count": len(temporal_slots), "region_count": len(regions),
        "first_timestamp": temporal_slots[0].timestamp if temporal_slots else None,
        "last_timestamp": temporal_slots[-1].timestamp if temporal_slots else None,
        "source_total_mbps": {
            "min": min(slot.total_demand_mbps for slot in temporal_slots),
            "max": max(slot.total_demand_mbps for slot in temporal_slots),
        } if temporal_slots else {},
        "scenario_hotspots": {name: list(ids) for name, ids in scenario_hotspots.items()},
        "sample_records": records,
        "maximum_conservation_error_mbps": max((record["conservation_error_mbps"] for record in records), default=0.0),
        "materialized_full_dataset": False,
    }
