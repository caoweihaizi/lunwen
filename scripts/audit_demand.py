#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.contracts import load_research_contract, load_simulation_contract
from mucar_demand.audit import audit_demand_pipeline, canonical_demand_hash
from mucar_demand.config import load_demand_contract
from mucar_demand.spatial import load_demand_regions
from mucar_demand.temporal import iter_temporal_slots


def _git_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _markdown(audit, validated_at):
    lines = [
        "# 第四阶段 OD 需求审计", "", f"- 状态：**{audit['status']}**",
        f"- 验证时间（UTC）：`{validated_at}`", f"- 时间间隔数：`{audit['temporal_slot_count']}`",
        f"- 地面区域数：`{audit['region_count']}`", f"- 时间范围：`{audit['first_timestamp']}` — `{audit['last_timestamp']}`",
        f"- 源总需求范围（Mbit/s）：`{audit['source_total_mbps']}`",
        f"- 最大守恒误差（Mbit/s）：`{audit['maximum_conservation_error_mbps']}`",
        f"- 全量 OD 已物化：`{audit['materialized_full_dataset']}`", "", "## 场景热点", "",
    ]
    for name, ids in audit["scenario_hotspots"].items():
        lines.append(f"- `{name}`: `{ids}`")
    lines.extend(["", "## 分区样本审计", "", "| slot | simulation time | partition | scenario | relative | base | scenario | mapped | local | backlog | error |", "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|"])
    for record in audit["sample_records"]:
        lines.append(
            f"| {record['time_slot']} | {record['simulation_timestamp_utc']} | {record['partition']} | {record['scenario']} | {record['relative_slot']} | "
            f"{record['base_total_mbps']:.6f} | {record['scenario_total_mbps']:.6f} | {record['mapped_satellite_od_mbps']:.6f} | "
            f"{record['local_delivery_mbps']:.6f} | {record['access_backlog_mbps']:.6f} | {record['conservation_error_mbps']:.3e} |"
        )
    lines.extend(["", f"- errors: `{len(audit['errors'])}`", f"- warnings: `{len(audit['warnings'])}`", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit factorized MUCAR ground OD demand.")
    parser.add_argument("--temporal", type=Path, default=ROOT / "data/processed/abilene/od_timeseries.csv.gz")
    parser.add_argument("--regions", type=Path, default=ROOT / "data/processed/geospatial/ground_regions.csv")
    parser.add_argument("--audit", type=Path, default=ROOT / "doc/第四阶段/demand_audit.md")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/manifests/stage4_demand_manifest.json")
    args = parser.parse_args(argv)
    try:
        demand = load_demand_contract(ROOT / "configs/demand_contract.yaml")
        research = load_research_contract(ROOT / "configs/research_contract.yaml")
        simulation = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")
        temporal = tuple(iter_temporal_slots(args.temporal))
        regions = load_demand_regions(args.regions)
        audit = audit_demand_pipeline(demand, research, simulation, temporal, regions)
    except (OSError, ValueError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    validated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {**audit, "canonical_sha256": canonical_demand_hash(audit), "validated_at_utc": validated_at, "git_commit": _git_commit()}
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(_markdown(audit, validated_at), encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"STAGE4_DEMAND_STATUS={audit['status']} errors={len(audit['errors'])} warnings={len(audit['warnings'])}")
    return 0 if audit["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
