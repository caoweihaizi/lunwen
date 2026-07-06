#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.contracts import ContractError, load_simulation_contract
from mucar_sim.audit import audit_one_orbit, canonical_audit_hash
from mucar_sim.coverage import load_ground_regions


def _git_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _render_markdown(audit, validated_at):
    lines = [
        "# 第三阶段动态星座审计", "",
        f"- 状态：**{audit['status']}**", f"- 验证时间（UTC）：`{validated_at}`",
        f"- 契约 SHA-256：`{audit['contract_sha256']}`", "", "## 轨道与 GMST", "",
        f"- Epoch：`{audit['epoch_utc']}`", f"- Julian Date：`{audit['julian_date_epoch']}`",
        f"- GMST（degree）：`{audit['gmst_epoch_deg']}`", f"- 轨道周期（s）：`{audit['orbit_period_s']}`",
        f"- 快照数：`{audit['snapshot_count']}`", f"- ECI 半径最大误差（km）：`{audit['maximum_eci_radius_error_km']}`",
        "", "## 拓扑", "",
        f"- 计划有向边数范围：`{audit['planned_directed_link_count']}`",
        f"- 计划无向边数范围：`{audit['planned_undirected_link_count']}`",
        f"- 节点度范围：`{audit['node_degree']}`", f"- 链路距离范围（km）：`{audit['link_distance_km']}`",
        "", "## 地面覆盖", "", f"- 区域数：`{audit['region_count']}`", "",
        "| region_id | min visible | mean visible | max visible | uncovered steps | max uncovered (s) | handovers | reattachments |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for region in audit["regions"]:
        lines.append(
            f"| {region['region_id']} | {region['min_visible_count']} | {region['mean_visible_count']:.6f} | "
            f"{region['max_visible_count']} | {region['uncovered_step_count']} | "
            f"{region['max_uncovered_duration_s']} | {region['handover_count']} | {region['reattachment_count']} |"
        )
    lines.extend(["", "## 错误与警告", "", f"- errors: `{len(audit['errors'])}`", f"- warnings: `{len(audit['warnings'])}`", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit one deterministic MUCAR Walker orbit.")
    parser.add_argument("--simulation", type=Path, default=ROOT / "configs/simulation_contract.yaml")
    parser.add_argument("--regions", type=Path)
    parser.add_argument("--audit", type=Path, default=ROOT / "doc/第三阶段/constellation_audit.md")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/manifests/stage3_constellation_manifest.json")
    args = parser.parse_args(argv)
    try:
        contract = load_simulation_contract(args.simulation)
        region_path = args.regions or ROOT / contract.coverage.ground_region_source
        regions = load_ground_regions(region_path)
    except (ContractError, OSError, ValueError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        audit = audit_one_orbit(contract, regions)
    except (ValueError, FloatingPointError) as exc:
        print(f"GEOMETRY_ERROR: {exc}", file=sys.stderr)
        return 3
    validated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        **audit,
        "canonical_sha256": canonical_audit_hash(audit),
        "validated_at_utc": validated_at,
        "git_commit": _git_commit(),
        "simulation_contract_path": str(Path(args.simulation).resolve().relative_to(ROOT)),
        "ground_region_path": str(Path(region_path).resolve().relative_to(ROOT)),
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(_render_markdown(audit, validated_at), encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"STAGE3_CONSTELLATION_STATUS={audit['status']} errors={len(audit['errors'])} warnings={len(audit['warnings'])}")
    return 0 if audit["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
