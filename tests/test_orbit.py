import math
import unittest
from pathlib import Path

import numpy as np

from mucar_data.contracts import load_simulation_contract
from mucar_sim.constellation import build_walker_constellation
from mucar_sim.coordinates import eci_to_ecef, gmst_degrees, julian_date_utc, normalize_longitude_deg
from mucar_sim.orbit import propagate


ROOT = Path(__file__).resolve().parents[1]


class OrbitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")
        cls.satellites = build_walker_constellation(cls.contract)

    def test_julian_date_and_gmst_reference_values(self):
        self.assertAlmostEqual(julian_date_utc("2000-01-01T12:00:00Z"), 2451545.0, places=10)
        self.assertAlmostEqual(gmst_degrees("2000-01-01T12:00:00Z"), 280.46061837, places=10)
        self.assertAlmostEqual(julian_date_utc(self.contract.time.epoch_utc), 2460676.5, places=10)
        self.assertAlmostEqual(gmst_degrees(self.contract.time.epoch_utc), 100.89956789370626, places=10)

    def test_longitude_normalization_is_half_open(self):
        self.assertEqual(normalize_longitude_deg(180.0), -180.0)
        self.assertEqual(normalize_longitude_deg(181.0), -179.0)

    def test_propagation_preserves_radius_shapes_ranges_and_arrays_are_readonly(self):
        snapshot = propagate(self.contract, self.satellites, 0)
        self.assertEqual(snapshot.eci_km.shape, (66, 3))
        self.assertEqual(snapshot.ecef_km.shape, (66, 3))
        np.testing.assert_allclose(np.linalg.norm(snapshot.eci_km, axis=1), self.contract.orbit_radius_km, rtol=0, atol=1e-9)
        np.testing.assert_allclose(np.linalg.norm(snapshot.ecef_km, axis=1), self.contract.orbit_radius_km, rtol=0, atol=1e-9)
        self.assertTrue(np.all((-90 <= snapshot.latitude_deg) & (snapshot.latitude_deg <= 90)))
        self.assertTrue(np.all((-180 <= snapshot.longitude_deg) & (snapshot.longitude_deg < 180)))
        self.assertFalse(snapshot.eci_km.flags.writeable)
        self.assertFalse(snapshot.ecef_km.flags.writeable)

    def test_epoch_ecef_rotation_uses_gmst(self):
        eci = np.array([[1.0, 0.0, 0.0]])
        ecef = eci_to_ecef(eci, self.contract.time.epoch_utc, 0, self.contract.earth.rotation_rad_s)
        angle = math.radians(-100.89956789370626)
        np.testing.assert_allclose(ecef[0], [math.cos(angle), math.sin(angle), 0.0], atol=1e-12)

    def test_ecef_rotation_after_one_day_uses_frozen_rotation_rate(self):
        eci = np.array([[1.0, 0.0, 0.0]])
        ecef = eci_to_ecef(eci, self.contract.time.epoch_utc, 86400, self.contract.earth.rotation_rad_s)
        theta = math.radians(100.89956789370626) + self.contract.earth.rotation_rad_s * 86400
        np.testing.assert_allclose(ecef[0], [math.cos(theta), -math.sin(theta), 0.0], atol=1e-12)

    def test_coordinate_inputs_reject_invalid_time_and_nonfinite_vectors(self):
        with self.assertRaises(ValueError):
            julian_date_utc("2025-01-01T00:00:00")
        with self.assertRaises(ValueError):
            eci_to_ecef(np.array([[np.nan, 0.0, 0.0]]), self.contract.time.epoch_utc, 0, self.contract.earth.rotation_rad_s)
        with self.assertRaises(ValueError):
            eci_to_ecef(np.array([1.0, 0.0, 0.0]), self.contract.time.epoch_utc, 0, self.contract.earth.rotation_rad_s)

    def test_integer_second_period_returns_near_initial_position(self):
        start = propagate(self.contract, self.satellites, 0)
        end = propagate(self.contract, self.satellites, int(round(self.contract.orbit_period_s)))
        displacement = np.linalg.norm(end.eci_km - start.eci_km, axis=1)
        self.assertLess(float(displacement.max()), 8.0)

    def test_negative_time_is_rejected(self):
        with self.assertRaises(ValueError):
            propagate(self.contract, self.satellites, -1)


if __name__ == "__main__":
    unittest.main()
