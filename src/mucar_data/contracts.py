import datetime as dt
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Tuple

import numpy as np
import yaml


class ContractError(ValueError):
    """Raised when a research or simulation contract is invalid."""


def _exact_keys(value, expected, path):
    if not isinstance(value, dict):
        raise ContractError(f"{path} must be a mapping")
    missing = set(expected) - set(value)
    unknown = set(value) - set(expected)
    if missing or unknown:
        raise ContractError(f"{path} fields invalid: missing={sorted(missing)} unknown={sorted(unknown)}")


def _type(value, expected, path):
    if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise ContractError(f"{path} must be int")
    if expected is float and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ContractError(f"{path} must be numeric")
    if expected not in (int, float) and not isinstance(value, expected):
        raise ContractError(f"{path} must be {expected.__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{path} must be finite")
    return value


def _reject_implicit_dates_and_nonfinite(value, path="root"):
    if isinstance(value, (dt.date, dt.datetime)):
        raise ContractError(f"{path} contains an implicit YAML date")
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{path} contains a non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_implicit_dates_and_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_implicit_dates_and_nonfinite(item, f"{path}[{index}]")


def _read_yaml(path):
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    _reject_implicit_dates_and_nonfinite(data)
    if not isinstance(data, dict):
        raise ContractError(f"{path} must contain a mapping")
    return data, hashlib.sha256(path.read_bytes()).hexdigest(), path


@dataclass(frozen=True)
class SplitContract:
    start: int
    stop: int
    count: int


@dataclass(frozen=True)
class ResearchContract:
    schema_version: str
    study_id: str
    title: str
    research_questions: Tuple[Mapping[str, str], ...]
    claim_boundaries: Mapping[str, bool]
    source_manifest_ids: Tuple[str, ...]
    total_traffic_slots: int
    splits: Mapping[str, SplitContract]
    window_crosses_split_boundary: bool
    fit_scalers_on: str
    tune_hyperparameters_on: Tuple[str, ...]
    conformal_initialization_on: str
    final_evaluation_on: str
    success_targets: Mapping[str, object]
    config_sha256: str
    source_path: Path

    @property
    def split_counts(self):
        return {name: split.count for name, split in self.splits.items()}


@dataclass(frozen=True)
class TimeContract:
    epoch_utc: str
    traffic_interval_s: int
    service_step_s: int
    routing_step_s: int
    orbit_update_s: int
    telemetry_step_s: int
    prediction_refresh_s: int
    prediction_horizons: Tuple[int, ...]


@dataclass(frozen=True)
class OrbitContract:
    constellation_type: str
    total_satellites: int
    planes: int
    satellites_per_plane: int
    phasing: int
    altitude_km: float
    inclination_deg: float
    eccentricity: float
    raan_span_deg: float
    raan_spacing_deg: float
    propagator: str


@dataclass(frozen=True)
class EarthContract:
    model: str
    radius_km: float
    mu_km3_s2: float
    rotation_rad_s: float
    light_speed_km_s: float


@dataclass(frozen=True)
class IslContract:
    storage: str
    intra_plane_neighbors: int
    inter_plane_neighbors_max: int
    connect_star_seam: bool
    inter_plane_pairing: str
    crosslink_max_abs_lat_deg: float
    require_earth_clearance: bool
    max_distance_km: float


@dataclass(frozen=True)
class LinkContract:
    capacity_mbps: float
    buffer_delay_budget_s: float
    max_wait_s: float
    queue_discipline: str
    update_order: str
    failed_link_service_mbit: float


@dataclass(frozen=True)
class CoverageContract:
    ground_region_source: str
    ground_altitude_km: float
    minimum_elevation_deg: float
    selection: str
    uncovered_behavior: str
    refresh_s: int


@dataclass(frozen=True)
class SeedContract:
    development: int
    formal: Tuple[int, ...]
    derivation: str
    key_order: Tuple[str, ...]
    module_ids: Mapping[str, int]


@dataclass(frozen=True)
class SimulationContract:
    schema_version: str
    time: TimeContract
    units: Mapping[str, str]
    orbit: OrbitContract
    earth: EarthContract
    isl: IslContract
    link: LinkContract
    coverage: CoverageContract
    demand_calibration: Mapping[str, object]
    seeds: SeedContract
    config_sha256: str
    source_path: Path

    @property
    def total_satellites(self): return self.orbit.total_satellites
    @property
    def planes(self): return self.orbit.planes
    @property
    def satellites_per_plane(self): return self.orbit.satellites_per_plane
    @property
    def traffic_interval_s(self): return self.time.traffic_interval_s
    @property
    def service_step_s(self): return self.time.service_step_s
    @property
    def orbit_update_s(self): return self.time.orbit_update_s
    @property
    def formal_seeds(self): return self.seeds.formal
    @property
    def orbit_radius_km(self): return self.earth.radius_km + self.orbit.altitude_km
    @property
    def mean_motion_rad_s(self): return math.sqrt(self.earth.mu_km3_s2 / self.orbit_radius_km ** 3)
    @property
    def orbit_period_s(self): return 2.0 * math.pi / self.mean_motion_rad_s
    @property
    def raan_deg(self): return tuple((plane * self.orbit.raan_spacing_deg) % 360.0 for plane in range(self.planes))
    @property
    def phase_deg(self):
        return tuple(
            (slot * 360.0 / self.satellites_per_plane + plane * 360.0 * self.orbit.phasing / self.total_satellites) % 360.0
            for plane in range(self.planes) for slot in range(self.satellites_per_plane)
        )
    @property
    def service_capacity_mbit(self): return self.link.capacity_mbps * self.service_step_s
    @property
    def buffer_capacity_mbit(self): return self.link.capacity_mbps * self.link.buffer_delay_budget_s
    @property
    def service_steps_per_traffic_interval(self): return self.traffic_interval_s // self.service_step_s
    @property
    def orbit_updates_per_traffic_interval(self): return self.traffic_interval_s // self.orbit_update_s


def load_research_contract(path):
    raw, digest, source_path = _read_yaml(path)
    _exact_keys(raw, {"schema_version", "study_id", "title", "research_questions", "claim_boundaries", "data", "success_targets"}, "research")
    _exact_keys(raw["claim_boundaries"], {"new_foundational_learning_theory", "unconditional_conformal_coverage_under_mar", "generalize_to_commercial_constellations", "generalize_to_onboard_hardware"}, "claim_boundaries")
    data_keys = {"source_manifest_ids", "total_traffic_slots", "splits", "window_crosses_split_boundary", "fit_scalers_on", "tune_hyperparameters_on", "conformal_initialization_on", "final_evaluation_on"}
    _exact_keys(raw["data"], data_keys, "data")
    _exact_keys(raw["success_targets"], {"target_interval_coverage", "accepted_coverage_min", "accepted_coverage_max", "quantile_crossing_rate", "formal_seed_count"}, "success_targets")
    if not isinstance(raw["research_questions"], list):
        raise ContractError("research_questions must be a list")
    questions = []
    for index, question in enumerate(raw["research_questions"]):
        _exact_keys(question, {"id", "text"}, f"research_questions[{index}]")
        questions.append({"id": _type(question["id"], str, "question.id"), "text": _type(question["text"], str, "question.text")})
    split_names = ("train", "validation", "calibration", "test")
    _exact_keys(raw["data"]["splits"], set(split_names), "data.splits")
    splits = {}
    for name in split_names:
        item = raw["data"]["splits"][name]
        _exact_keys(item, {"start", "stop", "count"}, f"data.splits.{name}")
        splits[name] = SplitContract(*(_type(item[key], int, f"data.splits.{name}.{key}") for key in ("start", "stop", "count")))
    return ResearchContract(
        _type(raw["schema_version"], str, "schema_version"), _type(raw["study_id"], str, "study_id"),
        _type(raw["title"], str, "title"), tuple(questions), dict(raw["claim_boundaries"]),
        tuple(raw["data"]["source_manifest_ids"]), _type(raw["data"]["total_traffic_slots"], int, "total_traffic_slots"),
        splits, _type(raw["data"]["window_crosses_split_boundary"], bool, "window_crosses_split_boundary"),
        _type(raw["data"]["fit_scalers_on"], str, "fit_scalers_on"), tuple(raw["data"]["tune_hyperparameters_on"]),
        _type(raw["data"]["conformal_initialization_on"], str, "conformal_initialization_on"),
        _type(raw["data"]["final_evaluation_on"], str, "final_evaluation_on"), dict(raw["success_targets"]), digest, source_path,
    )


def _dataclass_from(raw, name, cls, fields):
    _exact_keys(raw[name], set(fields), name)
    return cls(**{field: raw[name][field] for field in fields})


def load_simulation_contract(path):
    raw, digest, source_path = _read_yaml(path)
    sections = {"schema_version", "time", "units", "orbit", "earth", "isl", "link", "coverage", "demand_calibration", "seeds"}
    _exact_keys(raw, sections, "simulation")
    _type(raw["schema_version"], str, "schema_version")
    _exact_keys(raw["time"], set(TimeContract.__dataclass_fields__), "time")
    for field in ("traffic_interval_s", "service_step_s", "routing_step_s", "orbit_update_s", "telemetry_step_s", "prediction_refresh_s"):
        _type(raw["time"][field], int, f"time.{field}")
    _type(raw["time"]["epoch_utc"], str, "time.epoch_utc")
    if not isinstance(raw["time"]["prediction_horizons"], list) or not raw["time"]["prediction_horizons"]:
        raise ContractError("time.prediction_horizons must be a non-empty list")
    for index, horizon in enumerate(raw["time"]["prediction_horizons"]):
        _type(horizon, int, f"time.prediction_horizons[{index}]")
    time = TimeContract(**{
        key: tuple(value) if key == "prediction_horizons" else value
        for key, value in raw["time"].items()
    })
    orbit = _dataclass_from(raw, "orbit", OrbitContract, OrbitContract.__dataclass_fields__)
    earth = _dataclass_from(raw, "earth", EarthContract, EarthContract.__dataclass_fields__)
    isl = _dataclass_from(raw, "isl", IslContract, IslContract.__dataclass_fields__)
    link = _dataclass_from(raw, "link", LinkContract, LinkContract.__dataclass_fields__)
    coverage = _dataclass_from(raw, "coverage", CoverageContract, CoverageContract.__dataclass_fields__)
    for section_name, fields in {
        "orbit": ("total_satellites", "planes", "satellites_per_plane", "phasing"),
        "isl": ("intra_plane_neighbors", "inter_plane_neighbors_max"),
        "coverage": ("refresh_s",),
    }.items():
        for field in fields:
            _type(raw[section_name][field], int, f"{section_name}.{field}")
    for section_name, fields in {
        "orbit": ("altitude_km", "inclination_deg", "eccentricity", "raan_span_deg", "raan_spacing_deg"),
        "earth": ("radius_km", "mu_km3_s2", "rotation_rad_s", "light_speed_km_s"),
        "isl": ("crosslink_max_abs_lat_deg", "max_distance_km"),
        "link": ("capacity_mbps", "buffer_delay_budget_s", "max_wait_s", "failed_link_service_mbit"),
        "coverage": ("ground_altitude_km", "minimum_elevation_deg"),
    }.items():
        for field in fields:
            _type(raw[section_name][field], float, f"{section_name}.{field}")
    unit_fields = {"time", "distance", "speed", "rate", "volume", "delay", "configured_angle"}
    _exact_keys(raw["units"], unit_fields, "units")
    for field in unit_fields:
        _type(raw["units"][field], str, f"units.{field}")
    calibration_fields = {"allowed_split", "behavior_policy", "scenario", "statistic", "target", "accepted_min", "accepted_max", "search_min", "search_max", "max_iterations", "relative_tolerance"}
    _exact_keys(raw["demand_calibration"], calibration_fields, "demand_calibration")
    for field in ("target", "accepted_min", "accepted_max", "search_min", "search_max", "relative_tolerance"):
        _type(raw["demand_calibration"][field], float, f"demand_calibration.{field}")
    _type(raw["demand_calibration"]["max_iterations"], int, "demand_calibration.max_iterations")
    seed_fields = SeedContract.__dataclass_fields__
    _exact_keys(raw["seeds"], set(seed_fields), "seeds")
    _type(raw["seeds"]["development"], int, "seeds.development")
    for index, seed in enumerate(raw["seeds"]["formal"]):
        _type(seed, int, f"seeds.formal[{index}]")
    module_fields = {"demand", "burst", "failure", "missing", "behavior_policy", "model_init", "rl_env"}
    _exact_keys(raw["seeds"]["module_ids"], module_fields, "seeds.module_ids")
    for name in module_fields:
        _type(raw["seeds"]["module_ids"][name], int, f"seeds.module_ids.{name}")
    seeds = SeedContract(raw["seeds"]["development"], tuple(raw["seeds"]["formal"]), raw["seeds"]["derivation"], tuple(raw["seeds"]["key_order"]), dict(raw["seeds"]["module_ids"]))
    return SimulationContract(raw["schema_version"], time, dict(raw["units"]), orbit, earth, isl, link, coverage, dict(raw["demand_calibration"]), seeds, digest, source_path)


def derive_seed(master_seed, scenario_id, policy_id, module_id, replicate_id, seeds):
    if module_id not in seeds.module_ids:
        raise ContractError(f"unknown module_id: {module_id}")
    key = [master_seed, scenario_id, policy_id, seeds.module_ids[module_id], replicate_id]
    for index, value in enumerate(key):
        _type(value, int, f"seed_key[{index}]")
        if value < 0:
            raise ContractError("seed derivation keys must be nonnegative")
    return int(np.random.SeedSequence(key).generate_state(1, dtype=np.uint32)[0])


def validate_contract_pair(research, simulation):
    errors = []
    if research.schema_version != simulation.schema_version:
        errors.append("schema versions differ")
    if simulation.total_satellites != simulation.planes * simulation.satellites_per_plane:
        errors.append("Walker product does not equal total_satellites")
    for label, step in (("service", simulation.time.service_step_s), ("routing", simulation.time.routing_step_s), ("orbit", simulation.time.orbit_update_s), ("telemetry", simulation.time.telemetry_step_s)):
        if step <= 0 or simulation.traffic_interval_s % step:
            errors.append(f"traffic interval is not divisible by {label} step")
    if simulation.coverage.refresh_s != simulation.orbit_update_s:
        errors.append("coverage refresh must equal orbit update")
    if not 0.0 <= simulation.isl.crosslink_max_abs_lat_deg <= 90.0:
        errors.append("crosslink latitude threshold outside [0, 90]")
    if simulation.orbit.raan_spacing_deg * simulation.planes != simulation.orbit.raan_span_deg:
        errors.append("RAAN spacing and span disagree")
    expected_units = {"time": "s", "distance": "km", "speed": "km/s", "rate": "Mbit/s", "volume": "Mbit", "delay": "s", "configured_angle": "degree"}
    if dict(simulation.units) != expected_units:
        errors.append("units do not match the frozen internal unit contract")
    previous = 0
    for name in ("train", "validation", "calibration", "test"):
        split = research.splits[name]
        if split.start != previous or split.stop - split.start != split.count:
            errors.append(f"split {name} is non-contiguous or has an invalid count")
        previous = split.stop
    if previous != research.total_traffic_slots:
        errors.append("split boundaries do not cover total_traffic_slots")
    if len(set(simulation.formal_seeds)) != len(simulation.formal_seeds):
        errors.append("formal seeds must be unique")
    if len(simulation.formal_seeds) != research.success_targets["formal_seed_count"]:
        errors.append("formal seed count differs from success target")
    if simulation.seeds.development in simulation.formal_seeds:
        errors.append("development seed must not be a formal seed")
    if simulation.demand_calibration.get("allowed_split") != "train" or research.final_evaluation_on == "train":
        errors.append("demand calibration must use train and final evaluation must not use train")
    if errors:
        raise ContractError("; ".join(errors))
    derived = {
        "orbit_radius_km": simulation.orbit_radius_km,
        "mean_motion_rad_s": simulation.mean_motion_rad_s,
        "orbit_period_s": simulation.orbit_period_s,
        "raan_deg": list(simulation.raan_deg),
        "phase_deg": list(simulation.phase_deg),
        "service_capacity_mbit": simulation.service_capacity_mbit,
        "buffer_capacity_mbit": simulation.buffer_capacity_mbit,
        "service_steps_per_traffic_interval": simulation.service_steps_per_traffic_interval,
        "orbit_updates_per_traffic_interval": simulation.orbit_updates_per_traffic_interval,
        "split_boundaries": {name: {"start": value.start, "stop": value.stop, "count": value.count} for name, value in research.splits.items()},
    }
    return {"status": "PASS", "derived_values": derived, "warnings": [], "errors": [], "config_sha256": {"research": research.config_sha256, "simulation": simulation.config_sha256}}


def canonical_audit_json(audit):
    return json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
