import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mucar_data.contracts import load_simulation_contract
from mucar_sim.constellation import build_walker_constellation
from mucar_sim.audit import audit_one_orbit, canonical_audit_hash
from mucar_sim.coverage import GroundRegion


ROOT = Path(__file__).resolve().parents[1]


class ConstellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")

    def test_walker_ids_raan_and_phase_are_deterministic(self):
        satellites = build_walker_constellation(self.contract)
        self.assertEqual(len(satellites), 66)
        self.assertEqual(satellites[0].sat_id, "sat_p00_s00")
        self.assertEqual(satellites[-1].sat_id, "sat_p05_s10")
        self.assertEqual(tuple(s.raan_deg for s in satellites[::11]), self.contract.raan_deg)
        self.assertEqual(tuple(s.phase_deg for s in satellites), self.contract.phase_deg)
        self.assertEqual(len({s.sat_id for s in satellites}), 66)

    def test_small_region_orbit_audit_is_deterministic_and_complete(self):
        regions = (GroundRegion("equator", 0.0, 0.0), GroundRegion("north", 60.0, 10.0))
        first = audit_one_orbit(self.contract, regions)
        second = audit_one_orbit(self.contract, regions)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["satellite_count"], 66)
        self.assertEqual(first["region_count"], 2)
        self.assertGreater(first["snapshot_count"], 600)
        self.assertEqual(first["errors"], [])
        self.assertEqual(canonical_audit_hash(first), canonical_audit_hash(second))
        for region in first["regions"]:
            self.assertIn("max_uncovered_duration_s", region)
            self.assertIn("handover_count", region)

    def test_audit_cli_writes_markdown_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            audit_path = Path(td) / "audit.md"
            manifest_path = Path(td) / "manifest.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/audit_constellation.py"), "--audit", str(audit_path), "--manifest", str(manifest_path)],
                cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")}, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "STAGE3_CONSTELLATION_STATUS=PASS errors=0 warnings=0")
            self.assertIn("GMST", audit_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "PASS")
            self.assertEqual(manifest["region_count"], 980)
            self.assertEqual(len(manifest["canonical_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
