#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.config import load_config
from mucar_data.download import atomic_download
from mucar_data.manifest import build_manifest, write_manifest


FILENAMES = {
    "abilene": "directed-abilene-zhang-5min-over-6months-ALL-native.tgz",
    "worldpop": "global_pop_2025_CN_1km_R2025A_v1.tif",
    "timezone_boundaries": "timezones-with-oceans-now-2026b.geojson.zip",
}


def download_one(dataset_id, config, root):
    item = config[dataset_id]
    target = root / "data" / "raw" / dataset_id / FILENAMES[dataset_id]
    manifest_path = root / "data" / "manifests" / f"{dataset_id}.json"
    expected = None
    previous = None
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = previous.get("sha256")
    result = atomic_download(item["download_url"], target, expected_sha256=expected, timeout=120)
    manifest = build_manifest(
        dataset_id, item["role"], target, item,
        source_page=item["source_page"], requested_url=item["download_url"],
        final_url=(previous.get("final_url") if result.reused and previous else result.final_url),
        retrieved_at_utc=(previous.get("retrieved_at_utc") if result.reused and previous else result.retrieved_at_utc),
        release_version=item.get("release", item.get("version")),
        license=item.get("license", "REQUIRES_CONFIRMATION"),
        citation=item.get("doi", ""), media_type=result.headers.get("Content-Type", ""),
        response_headers=(previous.get("response_headers", {}) if result.reused and previous else result.headers),
        reused=result.reused,
    )
    write_manifest(manifest, manifest_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Download pinned MUCAR source datasets atomically.")
    parser.add_argument("datasets", nargs="*", choices=sorted(FILENAMES), default=list(FILENAMES))
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "data_sources.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    for dataset_id in args.datasets:
        manifest = download_one(dataset_id, config, ROOT)
        print(f"{dataset_id}: {manifest['byte_size']} bytes sha256={manifest['sha256']}")


if __name__ == "__main__":
    main()
