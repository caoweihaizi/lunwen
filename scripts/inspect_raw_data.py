#!/usr/bin/env python3
import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.abilene import dense_demands, iter_native_archive, timestamp_audit
from mucar_data.config import load_config


def inspect_abilene(path, expected):
    count = 0
    node_set = None
    timestamps = []
    nonzero_counts = []
    for matrix in iter_native_archive(path):
        count += 1
        if node_set is None:
            node_set = matrix.nodes
        elif matrix.nodes != node_set:
            raise ValueError(f"node order changed in {matrix.source_name}")
        dense = dense_demands(matrix)
        if len(dense) != expected["expected_directed_od_count"]:
            raise ValueError(f"unexpected OD count in {matrix.source_name}: {len(dense)}")
        timestamps.append(matrix.timestamp)
        nonzero_counts.append(sum(value > 0 for value in dense.values()))
    if count != expected["expected_matrix_count"]:
        raise ValueError(f"expected {expected['expected_matrix_count']} matrices, found {count}")
    if len(node_set or ()) != expected["expected_node_count"]:
        raise ValueError(f"unexpected node count: {len(node_set or ())}")
    time_report = timestamp_audit(timestamps)
    return {
        "matrix_count": count,
        "node_count": len(node_set),
        "directed_od_count": expected["expected_directed_od_count"],
        "first_timestamp": time_report["first_timestamp"],
        "last_timestamp": time_report["last_timestamp"],
        "archive_order_inversions": time_report["archive_order_inversions"],
        "minimum_nonzero_od_count": min(nonzero_counts),
        "maximum_nonzero_od_count": max(nonzero_counts),
    }


def environment_report():
    usage = shutil.disk_usage(ROOT)
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "disk_total_bytes": usage.total,
        "disk_free_bytes": usage.free,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit raw MUCAR source data.")
    parser.add_argument("--abilene", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "manifests" / "raw_data_audit.json")
    args = parser.parse_args()
    config = load_config(ROOT / "configs" / "data_sources.yaml")
    report = {"environment": environment_report()}
    if args.abilene:
        report["abilene"] = inspect_abilene(args.abilene, config["abilene"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
