import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ActivityConfig:
    floor: float
    amplitude: float
    peak_local_hour: float
    period_hours: float


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    scenario_id: int
    hotspot_count: int
    multiplier_start: float
    multiplier_end: float
    duration_slots: int


@dataclass(frozen=True)
class DemandContract:
    schema_version: str
    activity: ActivityConfig
    exclude_self_flows: bool
    conservation_abs_tolerance_mbps: float
    conservation_rel_tolerance: float
    scenarios: Mapping[str, ScenarioConfig]
    slots_per_split: int
    expected_temporal_slots: int
    expected_regions: int


def load_demand_contract(path: Path) -> DemandContract:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema_path = path.parent / "schemas/demand_contract.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.path))
    if errors:
        raise ValueError("; ".join(f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors))
    activity = ActivityConfig(**raw["activity"])
    scenarios = {name: ScenarioConfig(name=name, **values) for name, values in raw["scenarios"].items()}
    if len({scenario.scenario_id for scenario in scenarios.values()}) != len(scenarios):
        raise ValueError("scenario_id values must be unique")
    return DemandContract(
        schema_version=raw["schema_version"], activity=activity,
        exclude_self_flows=raw["od"]["exclude_self_flows"],
        conservation_abs_tolerance_mbps=raw["od"]["conservation_abs_tolerance_mbps"],
        conservation_rel_tolerance=raw["od"]["conservation_rel_tolerance"],
        scenarios=scenarios, slots_per_split=raw["audit"]["slots_per_split"],
        expected_temporal_slots=raw["audit"]["expected_temporal_slots"], expected_regions=raw["audit"]["expected_regions"],
    )
