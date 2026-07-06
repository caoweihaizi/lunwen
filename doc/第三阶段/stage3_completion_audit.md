# 第三阶段完成审计

## 结论

第三阶段“最小动态星座仿真器”的代码与正式审计产物已生成。最终结论以本文档记录的全量验证命令为准。

## 实现范围

- 66 星 Walker Star 66/6/2 确定性元数据；
- 解析二体圆轨道 ECI 传播；
- 固定 UTC epoch 的 Julian Date 与 GMST 初始角；
- ECI→ECEF→球形经纬度变换；
- 轨内 ISL、相邻平面跨轨互选 ISL、地球遮挡和高纬关闭；
- 有向计划拓扑与外部故障集驱动的运行拓扑纯过滤接口；
- 980 个地面区域的可见卫星、最大仰角接入和 backlog 映射；
- 单轨道周期审计和规范化哈希。

## 完成门槛与证据

| 门槛 | 证据 | 结论 |
|---|---|---|
| 66 星 ID、RAAN 与相位确定 | `tests/test_constellation.py` | 通过 |
| ECI/ECEF 半径守恒 | 最大误差 `1.8189894035458565e-12 km` | 通过 |
| 固定 epoch GMST | `JD=2460676.5`, `GMST=100.89956789370626°` | 通过 |
| 整秒周期回归 | `tests/test_orbit.py` 的 8 km 上限 | 通过 |
| 计划拓扑边对称 | 每快照反向边与距离一致 | 通过 |
| 节点度上限 | 整周期范围 `2–4` | 通过 |
| 链路距离上限 | 整周期范围 `2204.252–4033.360 km` | 通过 |
| 计划有向边数 | 整周期范围 `194–200` | 通过 |
| 空故障运行拓扑 | 每快照 `G_op == G_orb` | 通过 |
| 地面区域数 | 980 | 通过 |
| 无覆盖不静默映射 | `AccessAssignment.access_backlog` | 通过 |
| 不同 `PYTHONHASHSEED` 的规范化哈希 | `2b7dfeb4937640225c16a16030f0a91ada7561ad4ca8770aa588dfb88fb3a58b` | 通过 |
| 第一至第三阶段回归测试 | 45 项测试，0 failure / 0 error | 通过 |

## 覆盖结果与边界

- 单轨道周期共审计 604 个快照；
- 980 个区域中，311 个区域至少在一个快照处于无覆盖状态；
- 最长连续无覆盖时间为 130 s，小于一个 300 s 业务时隔；
- 本阶段保留该结果，由 `access_backlog` 显式承接，不把无覆盖区域映射到地平线以下的卫星；
- 此处的“未触发长时间空洞回退”按“持续时间小于一个业务时隔”判定。第四阶段不得删除 backlog 来美化覆盖。

## 可复现命令

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_contracts.py
PYTHONPATH=src .venv/bin/python scripts/audit_constellation.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests
git diff --check
```

## 产物

- `src/mucar_sim/`：星座、坐标、轨道、拓扑、覆盖和审计模块；
- `scripts/audit_constellation.py`：正式整周期审计入口；
- `tests/test_constellation.py`, `test_orbit.py`, `test_topology.py`, `test_coverage.py`：行为与回归测试；
- `doc/第三阶段/constellation_audit.md`：980 区域审计报告；
- `data/manifests/stage3_constellation_manifest.json`：机器可读审计与规范化哈希。
