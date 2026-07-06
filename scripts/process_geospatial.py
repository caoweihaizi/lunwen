#!/usr/bin/env python3
import csv
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.config import load_config
from mucar_data.geo import aggregate_population_grid, assign_timezones
from mucar_data.manifest import build_manifest, write_manifest


def main():
    config = load_config(ROOT / "configs/data_sources.yaml")
    raster = ROOT / "data/raw/worldpop/global_pop_2025_CN_1km_R2025A_v1.tif"
    timezone_zip = ROOT / "data/raw/timezone_boundaries/timezones-with-oceans-now-2026b.geojson.zip"
    regions, population_audit = aggregate_population_grid(raster, grid_degrees=5.0)
    with zipfile.ZipFile(timezone_zip) as archive:
        names = [name for name in archive.namelist() if name.endswith((".json", ".geojson"))]
        if len(names) != 1:
            raise ValueError(f"expected one GeoJSON file, found {names}")
        with archive.open(names[0]) as stream:
            timezone_data = json.load(stream)
    assigned, timezone_audit = assign_timezones(regions, timezone_data["features"])

    output = ROOT / "data/processed/geospatial/ground_regions.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["region_id", "centroid_lat", "centroid_lon", "population", "timezone", "population_weight", "timezone_match"]
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in assigned:
            writer.writerow({field: record[field] for field in fields})

    audit = {"population": population_audit, "timezone": timezone_audit}
    audit_path = ROOT / "data/manifests/geospatial_processing_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_hashes = {
        name: json.loads((ROOT / f"data/manifests/{name}.json").read_text(encoding="utf-8"))["sha256"]
        for name in ("worldpop", "timezone_boundaries")
    }
    manifest = build_manifest(
        "ground_regions", "spatial_population_weight", output,
        {"grid_degrees": 5.0, "source_hashes": source_hashes},
        generated_outputs=[str(output)], license="CC-BY-4.0 AND ODbL-1.0",
    )
    write_manifest(manifest, ROOT / "data/manifests/ground_regions.json")
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
