from typing import Sequence

import numpy as np

from mucar_data.contracts import SeedContract, derive_seed
from .config import ScenarioConfig
from .factorized import FactorizedOD
from .spatial import DemandRegion


def choose_hotspots(regions: Sequence[DemandRegion], scenario: ScenarioConfig, master_seed: int, seeds: SeedContract):
    if scenario.hotspot_count == 0:
        return ()
    if scenario.hotspot_count > len(regions):
        raise ValueError("hotspot_count exceeds region count")
    probabilities = np.asarray([region.population_weight for region in regions], dtype=float)
    probabilities /= probabilities.sum()
    seed = derive_seed(master_seed, scenario.scenario_id, 0, "burst", 0, seeds)
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(regions), size=scenario.hotspot_count, replace=False, p=probabilities)
    return tuple(sorted(regions[int(index)].region_id for index in chosen))


def scenario_multiplier(scenario: ScenarioConfig, relative_slot: int):
    if relative_slot < 0:
        raise ValueError("relative_slot must be nonnegative")
    if scenario.duration_slots == 0 or relative_slot >= scenario.duration_slots:
        return 1.0
    if scenario.duration_slots == 1:
        return scenario.multiplier_end
    fraction = relative_slot / (scenario.duration_slots - 1)
    return scenario.multiplier_start + (scenario.multiplier_end - scenario.multiplier_start) * fraction


def apply_intervention(base_od: FactorizedOD, scenario: ScenarioConfig, hotspot_ids, relative_slot: int):
    multiplier = scenario_multiplier(scenario, relative_slot)
    unknown = set(hotspot_ids) - set(base_od.region_ids)
    if unknown:
        raise ValueError(f"unknown hotspot IDs: {sorted(unknown)}")
    factors = np.ones(len(base_od.region_ids), dtype=float)
    hotspot_set = set(hotspot_ids)
    for index, region_id in enumerate(base_od.region_ids):
        if region_id in hotspot_set:
            factors[index] = multiplier
    changed = base_od.with_origin_multipliers(factors)
    return changed, {
        "scenario": scenario.name, "scenario_id": scenario.scenario_id,
        "relative_slot": relative_slot, "active": multiplier != 1.0,
        "multiplier": multiplier, "hotspot_ids": tuple(sorted(hotspot_ids)),
        "base_total_mbps": base_od.total_mbps, "scenario_total_mbps": changed.total_mbps,
    }
