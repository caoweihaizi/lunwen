#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.abilene import extract_native_archive, process_matrix_files
from mucar_data.config import load_config, split_counts
from mucar_data.manifest import build_manifest, write_manifest


def main():
    parser = argparse.ArgumentParser(description="Create deterministic processed MUCAR datasets.")
    parser.add_argument("--abilene", action="store_true")
    args = parser.parse_args()
    if not args.abilene:
        parser.error("select --abilene")
    config = load_config(ROOT / "configs" / "data_sources.yaml")
    archive = ROOT / "data/raw/abilene/directed-abilene-zhang-5min-over-6months-ALL-native.tgz"
    interim = ROOT / "data/interim/abilene"
    files = sorted(interim.glob("*.txt"))
    if len(files) != config["abilene"]["expected_matrix_count"]:
        files = extract_native_archive(archive, interim)
    train_count = split_counts(len(files), config["project"]["time_split"])[0]
    output = ROOT / "data/processed/abilene/od_timeseries.csv.gz"
    report = process_matrix_files(files, output, train_count=train_count)
    report_path = ROOT / "data/manifests/abilene_processing_audit.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = build_manifest(
        "abilene_processed", "temporal_od_pattern", output,
        {"source_sha256": json.loads((ROOT / "data/manifests/abilene.json").read_text())["sha256"],
         "time_split": config["project"]["time_split"]},
        generated_outputs=[str(output)],
    )
    write_manifest(manifest, ROOT / "data/manifests/abilene_processed.json")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
