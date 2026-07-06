#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.manifest import build_manifest, write_manifest


def main():
    parser = argparse.ArgumentParser(description="Build a traceability manifest for a local data asset.")
    parser.add_argument("dataset_id")
    parser.add_argument("role")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--processing-config", type=Path)
    args = parser.parse_args()
    processing = {}
    if args.processing_config:
        processing = json.loads(args.processing_config.read_text(encoding="utf-8"))
    write_manifest(build_manifest(args.dataset_id, args.role, args.source, processing), args.output)
    print(args.output)


if __name__ == "__main__":
    main()
