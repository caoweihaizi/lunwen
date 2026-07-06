#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mucar_data.contracts import ContractError, load_research_contract, load_simulation_contract, validate_contract_pair


def schema_errors(contract_path, schema_path):
    try:
        payload = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)]
    return sorted(
        (f"{'/'.join(str(x) for x in error.absolute_path) or '<root>'}: {error.message}" for error in Draft202012Validator(schema).iter_errors(payload)),
    )


def git_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def display_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def render_audit(audit, validated_at):
    derived = audit["derived_values"]
    lines = [
        "# 第二阶段契约审计", "", f"- 状态：**{audit['status']}**", f"- 验证时间（UTC）：`{validated_at}`",
        f"- 警告：{len(audit['warnings'])}", f"- 错误：{len(audit['errors'])}", "", "## 配置哈希", "",
        f"- research_contract.yaml：`{audit['config_sha256']['research']}`",
        f"- simulation_contract.yaml：`{audit['config_sha256']['simulation']}`", "", "## 派生量", "",
        "| 派生量 | 值 |", "|---|---:|",
        f"| 轨道半径 (km) | {derived['orbit_radius_km']:.6f} |",
        f"| 平均运动角速度 (rad/s) | {derived['mean_motion_rad_s']:.12f} |",
        f"| 轨道周期 (s) / orbit_period_s | {derived['orbit_period_s']:.6f} |",
        f"| 每业务时隔服务步数 | {derived['service_steps_per_traffic_interval']} |",
        f"| 每业务时隔轨道更新数 | {derived['orbit_updates_per_traffic_interval']} |",
        f"| 每服务步容量 (Mbit) | {derived['service_capacity_mbit']:.6f} |",
        f"| 缓存容量 (Mbit) | {derived['buffer_capacity_mbit']:.6f} |", "", "### RAAN", "",
        "`" + json.dumps(derived["raan_deg"], ensure_ascii=False) + "`", "", "### 四个分区边界", "",
        "| 分区 | start | stop | count |", "|---|---:|---:|---:|",
    ]
    for name, split in derived["split_boundaries"].items():
        lines.append(f"| {name} | {split['start']} | {split['stop']} | {split['count']} |")
    lines.extend([
        "", "## 冻结的简化假设", "",
        "- 球形地球，解析二体圆轨道，不使用真实 TLE。",
        "- FIFO 流量体积队列，不模拟逐包大小。",
        "- 全部 ISL 使用统一的有向链路容量。",
        "- 地面区域来自第一阶段 5° 非零人口网格。", "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate frozen MUCAR research and simulation contracts.")
    parser.add_argument("--research", type=Path, default=ROOT / "configs/research_contract.yaml")
    parser.add_argument("--simulation", type=Path, default=ROOT / "configs/simulation_contract.yaml")
    parser.add_argument("--audit", type=Path, default=ROOT / "doc/第二阶段/contract_audit.md")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/manifests/stage2_contract_manifest.json")
    args = parser.parse_args(argv)
    errors = []
    errors.extend(schema_errors(args.research, ROOT / "configs/schemas/research_contract.schema.json"))
    errors.extend(schema_errors(args.simulation, ROOT / "configs/schemas/simulation_contract.schema.json"))
    if errors:
        for error in errors:
            print(f"SCHEMA_ERROR: {error}", file=sys.stderr)
        return 2
    try:
        research = load_research_contract(args.research)
        simulation = load_simulation_contract(args.simulation)
        audit = validate_contract_pair(research, simulation)
    except ContractError as exc:
        print(f"CONTRACT_ERROR: {exc}", file=sys.stderr)
        return 3
    validated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        **audit,
        "schema_version": research.schema_version,
        "validated_at_utc": validated_at,
        "git_commit": git_commit(),
        "contracts": {
            "research": {"path": display_path(args.research), "sha256": research.config_sha256},
            "simulation": {"path": display_path(args.simulation), "sha256": simulation.config_sha256},
        },
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(render_audit(audit, validated_at), encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"STAGE2_CONTRACT_STATUS=PASS errors={len(audit['errors'])} warnings={len(audit['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
