import math
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from mucar_data.contracts import (
    ContractError,
    derive_seed,
    load_research_contract,
    load_simulation_contract,
    validate_contract_pair,
)


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / "configs/research_contract.yaml"
SIMULATION_PATH = ROOT / "configs/simulation_contract.yaml"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.research = load_research_contract(RESEARCH_PATH)
        self.simulation = load_simulation_contract(SIMULATION_PATH)

    def test_walker_time_buffer_splits_and_seeds_are_consistent(self):
        contract = self.simulation
        self.assertEqual(contract.total_satellites, contract.planes * contract.satellites_per_plane)
        self.assertEqual(contract.traffic_interval_s % contract.service_step_s, 0)
        self.assertEqual(contract.traffic_interval_s % contract.orbit_update_s, 0)
        self.assertEqual(contract.buffer_capacity_mbit, 500.0)
        self.assertEqual(sum(self.research.split_counts.values()), 48096)
        self.assertEqual(len(set(contract.formal_seeds)), 5)

    def test_orbit_and_time_derived_values_match_contract(self):
        contract = self.simulation
        self.assertAlmostEqual(contract.orbit_radius_km, 7158.137)
        expected_motion = math.sqrt(398600.4418 / contract.orbit_radius_km ** 3)
        self.assertAlmostEqual(contract.mean_motion_rad_s, expected_motion)
        self.assertAlmostEqual(contract.orbit_period_s, 2 * math.pi / expected_motion)
        self.assertEqual(contract.raan_deg, (0.0, 30.0, 60.0, 90.0, 120.0, 150.0))
        self.assertEqual(len(contract.phase_deg), 66)
        self.assertEqual(contract.service_steps_per_traffic_interval, 300)
        self.assertEqual(contract.orbit_updates_per_traffic_interval, 30)
        self.assertEqual(contract.service_capacity_mbit, 1000.0)

    def test_contract_pair_audit_is_serializable_and_clean(self):
        audit = validate_contract_pair(self.research, self.simulation)
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["warnings"], [])
        self.assertEqual(audit["errors"], [])
        self.assertEqual(set(audit["config_sha256"]), {"research", "simulation"})
        self.assertIn("orbit_period_s", audit["derived_values"])

    def test_seed_derivation_is_stable_and_module_specific(self):
        first = derive_seed(202501, 4, 2, "demand", 0, self.simulation.seeds)
        second = derive_seed(202501, 4, 2, "demand", 0, self.simulation.seeds)
        other = derive_seed(202501, 4, 2, "failure", 0, self.simulation.seeds)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 2**32 - 1)

    def test_unknown_missing_implicit_date_and_nonfinite_values_are_rejected(self):
        research = yaml.safe_load(RESEARCH_PATH.read_text(encoding="utf-8"))
        simulation = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8"))
        cases = []
        unknown = dict(simulation)
        unknown["unexpected"] = 1
        cases.append(("simulation", unknown))
        missing = dict(simulation)
        missing.pop("earth")
        cases.append(("simulation", missing))
        implicit_date = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8").replace('"2025-01-01T00:00:00Z"', "2025-01-01"))
        cases.append(("simulation", implicit_date))
        nonfinite = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8"))
        nonfinite["earth"]["radius_km"] = float("nan")
        cases.append(("simulation", nonfinite))
        with tempfile.TemporaryDirectory() as td:
            for index, (kind, payload) in enumerate(cases):
                with self.subTest(index=index):
                    path = Path(td) / f"case-{index}.yaml"
                    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
                    with self.assertRaises(ContractError):
                        (load_research_contract if kind == "research" else load_simulation_contract)(path)

    def test_loader_rejects_nested_unknown_fields_and_bool_as_integer(self):
        simulation = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8"))
        nested_unknown = yaml.safe_load(yaml.safe_dump(simulation))
        nested_unknown["demand_calibration"]["extra"] = 1
        bool_integer = yaml.safe_load(yaml.safe_dump(simulation))
        bool_integer["time"]["service_step_s"] = True
        with tempfile.TemporaryDirectory() as td:
            for index, payload in enumerate((nested_unknown, bool_integer)):
                with self.subTest(index=index):
                    path = Path(td) / f"strict-{index}.yaml"
                    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
                    with self.assertRaises(ContractError):
                        load_simulation_contract(path)

    def test_cross_constraints_reject_invalid_time_split_seed_and_latitude(self):
        base_research = yaml.safe_load(RESEARCH_PATH.read_text(encoding="utf-8"))
        base_simulation = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8"))
        mutations = []
        bad_time = yaml.safe_load(yaml.safe_dump(base_simulation))
        bad_time["time"]["orbit_update_s"] = 7
        mutations.append((base_research, bad_time))
        bad_split = yaml.safe_load(yaml.safe_dump(base_research))
        bad_split["data"]["splits"]["validation"]["start"] = 28000
        mutations.append((bad_split, base_simulation))
        bad_seed = yaml.safe_load(yaml.safe_dump(base_simulation))
        bad_seed["seeds"]["formal"][1] = bad_seed["seeds"]["formal"][0]
        mutations.append((base_research, bad_seed))
        bad_latitude = yaml.safe_load(yaml.safe_dump(base_simulation))
        bad_latitude["isl"]["crosslink_max_abs_lat_deg"] = 91.0
        mutations.append((base_research, bad_latitude))
        with tempfile.TemporaryDirectory() as td:
            for index, (research, simulation) in enumerate(mutations):
                with self.subTest(index=index):
                    research_path = Path(td) / f"research-{index}.yaml"
                    simulation_path = Path(td) / f"simulation-{index}.yaml"
                    research_path.write_text(yaml.safe_dump(research, allow_unicode=True), encoding="utf-8")
                    simulation_path.write_text(yaml.safe_dump(simulation, allow_unicode=True), encoding="utf-8")
                    with self.assertRaises(ContractError):
                        validate_contract_pair(
                            load_research_contract(research_path),
                            load_simulation_contract(simulation_path),
                        )

    def test_json_schemas_accept_frozen_contracts_and_reject_unknown_fields(self):
        for name, contract_path in (("research", RESEARCH_PATH), ("simulation", SIMULATION_PATH)):
            with self.subTest(name=name):
                schema_path = ROOT / f"configs/schemas/{name}_contract.schema.json"
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                validator = Draft202012Validator(schema)
                payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
                self.assertEqual(list(validator.iter_errors(payload)), [])
                payload["unexpected"] = True
                self.assertTrue(list(validator.iter_errors(payload)))

    def test_validator_cli_writes_audit_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.md"
            manifest = Path(td) / "manifest.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_contracts.py"), "--audit", str(audit), "--manifest", str(manifest)],
                cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "STAGE2_CONTRACT_STATUS=PASS errors=0 warnings=0")
            self.assertIn("orbit_period_s", audit.read_text(encoding="utf-8"))
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["schema_version"], "1.0")

    def test_validator_cli_uses_exit_code_two_for_schema_errors_and_three_for_cross_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            research = yaml.safe_load(RESEARCH_PATH.read_text(encoding="utf-8"))
            simulation = yaml.safe_load(SIMULATION_PATH.read_text(encoding="utf-8"))
            research["unexpected"] = 1
            bad_schema = root / "bad-schema.yaml"
            bad_schema.write_text(yaml.safe_dump(research, allow_unicode=True), encoding="utf-8")
            simulation["time"]["orbit_update_s"] = 7
            bad_cross = root / "bad-cross.yaml"
            bad_cross.write_text(yaml.safe_dump(simulation, allow_unicode=True), encoding="utf-8")
            schema_result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_contracts.py"), "--research", str(bad_schema)],
                cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")}, capture_output=True,
            )
            cross_result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_contracts.py"), "--simulation", str(bad_cross)],
                cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")}, capture_output=True,
            )
            self.assertEqual(schema_result.returncode, 2)
            self.assertEqual(cross_result.returncode, 3)


if __name__ == "__main__":
    unittest.main()
