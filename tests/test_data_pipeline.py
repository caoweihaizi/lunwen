import hashlib
import json
import math
import tempfile
import tarfile
import unittest
from io import BytesIO
from pathlib import Path

from mucar_data.abilene import dense_demands, iter_native_archive, normalize_records, parse_native_matrix, process_matrix_files, timestamp_audit
from mucar_data.download import atomic_download, byte_ranges
from mucar_data.geo import aggregate_population_grid, assign_timezones, normalize_longitude, normalize_population
from mucar_data.manifest import build_manifest, verify_manifest
from mucar_data.config import load_config, split_counts


FIXTURE = """?SNDlib native format; type: network; version: 1.0
NODES (
 A ( 0.0 0.0 )
 B ( 0.0 0.0 )
 C ( 0.0 0.0 )
)
DEMANDS (
 d1 A B 1.5 UNLIMITED 0 0
 d2 B A 2.5 UNLIMITED 0 0
 d3 C A 0.0 UNLIMITED 0 0
)
META (
 TIMESTAMP 2004-03-01-00-00
)
"""

REAL_FORMAT_FIXTURE = """META (
  granularity = 5min
  time = 20040301-0010
  unit = MBITPERSEC
)
NODES (
  ATLAM5 ( -84.3833 33.75 )
  ATLAng ( -85.50 34.50 )
)
LINKS (
)
DEMANDS (
  ATLAM5_ATLAng ( ATLAM5 ATLAng ) 1 0.375261 UNLIMITED
  ATLAng_ATLAM5 ( ATLAng ATLAM5 ) 1 0.462461 UNLIMITED
)
"""


class AbileneTests(unittest.TestCase):
    def test_parse_real_sndlib_demand_and_time_syntax(self):
        matrix = parse_native_matrix(REAL_FORMAT_FIXTURE, source_name="real.txt")
        self.assertEqual(matrix.timestamp, "20040301-0010")
        self.assertEqual([(x.src, x.dst, x.value) for x in matrix.demands], [
            ("ATLAM5", "ATLAng", 0.375261), ("ATLAng", "ATLAM5", 0.462461)
        ])

    def test_parse_native_matrix_extracts_timestamp_nodes_and_nonnegative_demands(self):
        matrix = parse_native_matrix(FIXTURE, source_name="fixture.txt")
        self.assertEqual(matrix.timestamp, "2004-03-01-00-00")
        self.assertEqual(matrix.nodes, ("A", "B", "C"))
        self.assertEqual([(x.src, x.dst, x.value) for x in matrix.demands], [
            ("A", "B", 1.5), ("B", "A", 2.5), ("C", "A", 0.0)
        ])

    def test_parser_rejects_negative_or_nonfinite_demand(self):
        for bad in ("-1.0", "nan", "inf"):
            with self.subTest(bad=bad):
                text = FIXTURE.replace("1.5 UNLIMITED", f"{bad} UNLIMITED")
                with self.assertRaises(ValueError):
                    parse_native_matrix(text, source_name="bad.txt")

    def test_normalization_uses_training_only_median_and_handles_zero_total(self):
        records = [
            [("A", "B", 2.0), ("B", "A", 2.0)],
            [("A", "B", 4.0), ("B", "A", 4.0)],
            [("A", "B", 0.0), ("B", "A", 0.0)],
            [("A", "B", 1000.0), ("B", "A", 1000.0)],
        ]
        out, metadata = normalize_records(records, train_count=2)
        self.assertEqual(metadata["training_total_median"], 6.0)
        self.assertAlmostEqual(out[0][0]["global_intensity"], 4.0 / 6.0)
        self.assertEqual(out[2][0]["global_intensity"], 0.0)
        self.assertEqual(out[2][0]["od_share"], 0.0)
        self.assertEqual(metadata["zero_total_slots"], 1)

    def test_dense_demands_materializes_omitted_zero_pairs(self):
        matrix = parse_native_matrix(FIXTURE, source_name="fixture.txt")
        dense = dense_demands(matrix)
        self.assertEqual(len(dense), 6)
        self.assertEqual(dense[("A", "C")], 0.0)
        self.assertEqual(dense[("A", "B")], 1.5)

    def test_archive_reader_rejects_unsafe_member_names(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "unsafe.tgz"
            with tarfile.open(archive, "w:gz") as tar:
                payload = FIXTURE.encode()
                info = tarfile.TarInfo("../escape.txt")
                info.size = len(payload)
                tar.addfile(info, BytesIO(payload))
            with self.assertRaises(ValueError):
                list(iter_native_archive(archive))

    def test_timestamp_audit_accepts_unique_archive_order_and_reports_inversions(self):
        audit = timestamp_audit(["20040301-0010", "20040301-0000", "20040301-0020"])
        self.assertEqual(audit["unique_count"], 3)
        self.assertEqual(audit["archive_order_inversions"], 1)
        self.assertEqual(audit["first_timestamp"], "20040301-0000")
        with self.assertRaises(ValueError):
            timestamp_audit(["20040301-0000", "20040301-0000"])

    def test_processed_csv_gzip_is_deterministic_and_sorted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            late = root / "late.txt"
            early = root / "early.txt"
            late.write_text(REAL_FORMAT_FIXTURE.replace("20040301-0010", "20040301-0020"), encoding="utf-8")
            early.write_text(REAL_FORMAT_FIXTURE, encoding="utf-8")
            first = root / "first.csv.gz"
            second = root / "second.csv.gz"
            a = process_matrix_files([late, early], first, train_count=1)
            b = process_matrix_files([early, late], second, train_count=1)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(a["matrix_count"], 2)
            self.assertEqual(a["first_timestamp"], "20040301-0010")
            self.assertEqual(a["sha256"], b["sha256"])


class DownloadAndManifestTests(unittest.TestCase):
    def test_byte_ranges_cover_asset_exactly_without_overlap(self):
        self.assertEqual(byte_ranges(10, 3), [(0, 3), (4, 7), (8, 9)])

    def test_atomic_download_reuses_matching_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "asset.bin"
            target.write_bytes(b"stable")
            expected = hashlib.sha256(b"stable").hexdigest()
            result = atomic_download("unused://url", target, expected_sha256=expected)
            self.assertTrue(result.reused)
            self.assertEqual(target.read_bytes(), b"stable")

    def test_manifest_detects_changed_source(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.dat"
            source.write_bytes(b"original")
            manifest = build_manifest("fixture", "test", source, {"a": 1})
            self.assertTrue(verify_manifest(manifest))
            source.write_bytes(b"changed")
            self.assertFalse(verify_manifest(manifest))

    def test_repository_config_has_pinned_assets_and_valid_split(self):
        config = load_config(Path("configs/data_sources.yaml"))
        self.assertNotIn("latest", config["timezone_boundaries"]["download_url"])
        self.assertEqual(config["worldpop"]["release"], "R2025A")
        self.assertIsInstance(config["abilene"]["calendar_start"], str)
        self.assertEqual(split_counts(48096, config["project"]["time_split"]), (28857, 7214, 4809, 7216))


class GeoTests(unittest.TestCase):
    def test_windowed_population_aggregation_excludes_nodata(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "population.tif"
            with rasterio.open(
                source, "w", driver="GTiff", width=4, height=2, count=1,
                dtype="float32", crs="EPSG:4326", transform=from_origin(-180, 90, 90, 90), nodata=-9999,
            ) as dst:
                dst.write(np.array([[1, 2, -9999, 4], [5, 6, 7, 8]], dtype="float32"), 1)
            regions, audit = aggregate_population_grid(source, grid_degrees=90)
            self.assertEqual(audit["valid_population_total"], 33.0)
            self.assertEqual(audit["invalid_cell_count"], 1)
            self.assertEqual(sum(x["population"] for x in regions), 33.0)
            self.assertLess(abs(sum(x["population_weight"] for x in regions) - 1.0), 1e-8)

    def test_timezone_assignment_uses_geojson_polygons(self):
        features = [
            {"type": "Feature", "properties": {"tzid": "West/Test"},
             "geometry": {"type": "Polygon", "coordinates": [[[-180,-90],[0,-90],[0,90],[-180,90],[-180,-90]]]}},
            {"type": "Feature", "properties": {"tzid": "East/Test"},
             "geometry": {"type": "Polygon", "coordinates": [[[0,-90],[180,-90],[180,90],[0,90],[0,-90]]]}},
        ]
        regions = [{"centroid_lon": -10.0, "centroid_lat": 0.0}, {"centroid_lon": 10.0, "centroid_lat": 0.0}]
        assigned, audit = assign_timezones(regions, features)
        self.assertEqual([x["timezone"] for x in assigned], ["West/Test", "East/Test"])
        self.assertEqual(audit["unmatched_region_count"], 0)

    def test_population_weights_exclude_invalid_cells_and_sum_to_one(self):
        values = [10.0, 30.0, -1.0, float("nan")]
        weights, valid = normalize_population(values, nodata=-1.0)
        self.assertEqual(valid, [True, True, False, False])
        self.assertEqual(weights[2:], [0.0, 0.0])
        self.assertLess(abs(sum(weights) - 1.0), 1e-8)

    def test_longitudes_are_canonical_across_dateline(self):
        self.assertEqual(normalize_longitude(180.0), -180.0)
        self.assertEqual(normalize_longitude(181.0), -179.0)
        self.assertEqual(normalize_longitude(-181.0), 179.0)
        self.assertTrue(math.isclose(normalize_longitude(179.5), 179.5))


if __name__ == "__main__":
    unittest.main()
