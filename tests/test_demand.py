import gzip
import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from mucar_data.contracts import load_simulation_contract
from mucar_demand.access import aggregate_to_satellites
from mucar_demand.calibration import calibrate_demand_scale
from mucar_demand.config import load_demand_contract
from mucar_demand.factorized import FactorizedOD
from mucar_demand.interventions import apply_intervention, choose_hotspots
from mucar_demand.spatial import DemandRegion, activity_multiplier, spatial_weights
from mucar_demand.temporal import iter_temporal_slots, simulation_datetime
from mucar_sim.coverage import AccessAssignment


ROOT = Path(__file__).resolve().parents[1]


class DemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demand_contract = load_demand_contract(ROOT / "configs/demand_contract.yaml")
        cls.simulation_contract = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")

    def test_activity_profile_and_timezone_weights(self):
        self.assertAlmostEqual(activity_multiplier(14.0, self.demand_contract.activity), 1.0)
        self.assertAlmostEqual(activity_multiplier(2.0, self.demand_contract.activity), 0.35)
        regions = (
            DemandRegion("utc", 0, 0, 100, "UTC", 0.5),
            DemandRegion("tokyo", 0, 0, 100, "Asia/Tokyo", 0.5),
        )
        weights = spatial_weights(regions, datetime(2025, 1, 1, 5, tzinfo=timezone.utc), self.demand_contract)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=12)
        self.assertNotEqual(weights[0], weights[1])

    def test_factorized_od_excludes_self_and_conserves_total(self):
        od = FactorizedOD.from_weights(60.0, ("a", "b", "c"), np.array([0.2, 0.3, 0.5]), np.array([0.2, 0.3, 0.5]))
        matrix = od.materialize()
        self.assertTrue(np.all(np.diag(matrix) == 0))
        self.assertTrue(np.all(matrix >= 0))
        self.assertAlmostEqual(float(matrix.sum()), 60.0)
        self.assertAlmostEqual(od.total_mbps, 60.0)

    def test_intervention_multiplies_only_hotspot_origins_without_mutating_base(self):
        base = FactorizedOD.from_weights(100.0, ("a", "b", "c"), np.array([0.2, 0.3, 0.5]), np.array([0.2, 0.3, 0.5]))
        before = base.materialize().copy()
        scenario = self.demand_contract.scenarios["local_burst"]
        changed, metadata = apply_intervention(base, scenario, ("b",), 0)
        np.testing.assert_allclose(base.materialize(), before)
        np.testing.assert_allclose(changed.materialize()[1], before[1] * 4.0)
        np.testing.assert_allclose(changed.materialize()[[0, 2]], before[[0, 2]])
        self.assertEqual(metadata["multiplier"], 4.0)
        inactive, metadata = apply_intervention(base, scenario, ("b",), scenario.duration_slots)
        np.testing.assert_allclose(inactive.materialize(), before)
        self.assertEqual(metadata["multiplier"], 1.0)

    def test_hotspot_selection_is_reproducible(self):
        regions = tuple(DemandRegion(str(i), 0, 0, i + 1, "UTC", (i + 1) / 15) for i in range(5))
        scenario = self.demand_contract.scenarios["local_burst"]
        first = choose_hotspots(regions, scenario, 202500, self.simulation_contract.seeds)
        second = choose_hotspots(regions, scenario, 202500, self.simulation_contract.seeds)
        self.assertEqual(first, second)

    def test_demand_scale_bisection_uses_frozen_search_contract(self):
        calibration = self.simulation_contract.demand_calibration
        result = calibrate_demand_scale(lambda scale: scale / 10.0, calibration)
        self.assertGreaterEqual(result.statistic, calibration["accepted_min"])
        self.assertLessEqual(result.statistic, calibration["accepted_max"])
        self.assertAlmostEqual(result.scale, 6.0, delta=0.2)
        with self.assertRaises(ValueError):
            calibrate_demand_scale(lambda scale: 0.0, calibration)

    def test_satellite_aggregation_conserves_mapped_local_and_backlog(self):
        od = FactorizedOD.from_weights(60.0, ("a", "b", "c"), np.array([0.2, 0.3, 0.5]), np.array([0.2, 0.3, 0.5]))
        assignments = (
            AccessAssignment("a", 1, "s1", 30, False),
            AccessAssignment("b", 1, "s1", 30, False),
            AccessAssignment("c", 0, None, None, True),
        )
        result = aggregate_to_satellites(od, assignments)
        self.assertAlmostEqual(result.satellite_od_mbps + result.local_delivery_mbps + result.access_backlog_mbps, od.total_mbps)
        self.assertGreater(result.local_delivery_mbps, 0)
        self.assertGreater(result.access_backlog_mbps, 0)

    def test_temporal_reader_rejects_inconsistent_rows(self):
        header = "timestamp_index,timestamp,src_id,dst_id,demand_raw,total_demand,global_intensity,od_share\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
                stream.write(header)
                stream.write("0,20040301-0000,a,b,1,10,1,0.1\n")
                stream.write("0,20040301-0000,b,a,1,11,1,0.1\n")
            with self.assertRaises(ValueError):
                tuple(iter_temporal_slots(path, expected_rows_per_slot=2))

    def test_temporal_reader_preserves_official_calendar_gaps_with_contiguous_indices(self):
        header = "timestamp_index,timestamp,src_id,dst_id,demand_raw,total_demand,global_intensity,od_share\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "gap.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
                stream.write(header)
                stream.write("0,20040314-2355,a,b,1,10,1,0.1\n")
                stream.write("1,20040402-0000,a,b,1,11,1,0.1\n")
            slots = tuple(iter_temporal_slots(path, expected_rows_per_slot=1))
            self.assertEqual([slot.timestamp_index for slot in slots], [0, 1])
            self.assertGreater((slots[1].source_timestamp_utc - slots[0].source_timestamp_utc).total_seconds(), 300)

    def test_simulation_time_remains_continuous_across_source_calendar_gap(self):
        left = simulation_datetime(self.simulation_contract, 4031)
        right = simulation_datetime(self.simulation_contract, 4032)
        self.assertEqual((right - left).total_seconds(), 300)
        self.assertEqual(simulation_datetime(self.simulation_contract, 0).isoformat(), "2025-01-01T00:00:00+00:00")

    def test_demand_audit_cli_writes_pass_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.md"
            manifest = Path(td) / "manifest.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/audit_demand.py"), "--audit", str(audit), "--manifest", str(manifest)],
                cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "STAGE4_DEMAND_STATUS=PASS errors=0 warnings=0")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["temporal_slot_count"], 48096)
            self.assertEqual(data["region_count"], 980)
            self.assertEqual(len(data["canonical_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
