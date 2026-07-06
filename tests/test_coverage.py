import tempfile
import unittest
from pathlib import Path

import numpy as np

from mucar_data.contracts import load_simulation_contract
from mucar_sim.constellation import build_walker_constellation
from mucar_sim.coverage import GroundRegion, assign_access, load_ground_regions
from mucar_sim.orbit import PositionSnapshot, propagate


ROOT = Path(__file__).resolve().parents[1]


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")
        cls.satellites = build_walker_constellation(cls.contract)

    def test_ground_region_loader_validates_ids_and_coordinates(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.csv"
            good.write_text("region_id,centroid_lat,centroid_lon,extra\na,10,20,x\nb,-10,-20,y\n", encoding="utf-8")
            self.assertEqual(len(load_ground_regions(good)), 2)
            duplicate = Path(td) / "duplicate.csv"
            duplicate.write_text("region_id,centroid_lat,centroid_lon\na,0,0\na,1,1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_ground_regions(duplicate)
            bad = Path(td) / "bad.csv"
            bad.write_text("region_id,centroid_lat,centroid_lon\na,91,0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_ground_regions(bad)
            nonfinite = Path(td) / "nonfinite.csv"
            nonfinite.write_text("region_id,centroid_lat,centroid_lon\na,nan,0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_ground_regions(nonfinite)

    def test_access_assignment_selects_zenith_and_marks_backlog(self):
        radius = self.contract.earth.radius_km
        altitude = self.contract.orbit.altitude_km
        ecef = np.array([[radius + altitude, 0, 0], [-(radius + altitude), 0, 0]], dtype=float)
        arrays = [ecef.copy(), ecef.copy(), np.array([0.0, 0.0]), np.array([0.0, 180.0])]
        for array in arrays:
            array.flags.writeable = False
        positions = PositionSnapshot(0, ("sat_a", "sat_b"), arrays[0], arrays[1], arrays[2], arrays[3])
        regions = (GroundRegion("covered", 0.0, 0.0), GroundRegion("hidden", 0.0, 90.0))
        assignments = assign_access(self.contract, positions, regions)
        self.assertEqual(assignments[0].selected_sat_id, "sat_a")
        self.assertAlmostEqual(assignments[0].selected_elevation_deg, 90.0)
        self.assertTrue(assignments[1].access_backlog)
        self.assertIsNone(assignments[1].selected_sat_id)

    def test_equal_elevation_tie_uses_satellite_id_not_input_order(self):
        radius = self.contract.earth.radius_km + self.contract.orbit.altitude_km
        ecef = np.array([[radius, 0, 0], [radius, 0, 0]], dtype=float)
        arrays = [ecef.copy(), ecef.copy(), np.zeros(2), np.zeros(2)]
        for array in arrays:
            array.flags.writeable = False
        positions = PositionSnapshot(0, ("sat_b", "sat_a"), arrays[0], arrays[1], arrays[2], arrays[3])
        assignment = assign_access(self.contract, positions, (GroundRegion("r", 0.0, 0.0),))[0]
        self.assertEqual(assignment.selected_sat_id, "sat_a")

    def test_real_ground_region_count_when_processed_data_exists(self):
        path = ROOT / self.contract.coverage.ground_region_source
        if not path.exists():
            self.skipTest(f"processed ground regions unavailable: {path}")
        self.assertEqual(len(load_ground_regions(path)), 980)


if __name__ == "__main__":
    unittest.main()
