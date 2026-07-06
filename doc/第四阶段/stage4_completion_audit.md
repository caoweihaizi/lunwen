# 第四阶段完成审计

## 结论

第四阶段 OD 需求生成器已按因子化、先干预后接入和全局总量守恒设计实现。

## 完成门槛

| 门槛 | 证据 | 结论 |
|---|---|---|
| Abilene 时间索引 | 48,096 个连续 `timestamp_index` | 通过 |
| 原始日历语义 | 严格递增，保留官方采集间断 | 通过 |
| 地面区域 | 980 个人口—时区区域 | 通过 |
| 空间权重 | 每审计 slot 非负、有限、总和为 1 | 通过 |
| 非自环 OD | 对角线为 0，基础总量守恒 | 通过 |
| 四场景干预 | normal/burst/hotspot/drift 先于接入映射 | 通过 |
| 接入聚合 | 卫星对 + 本地交付 + backlog 守恒 | 通过 |
| 最大守恒误差 | `6.821210263296962e-12 Mbit/s` | 通过 |
| 全量物化 | `materialized_full_dataset=false` | 通过 |
| 复现哈希 | `3719e05b5494731c9945f222556a37e9e49d8dac2f53297969287ccd4cc8e350` | 通过 |
| 第一至第四阶段全量测试 | 55 项，0 failure / 0 error | 通过 |

## 重要边界

- `total_demand` 是未缩放的 Mbit/s 总量，`global_intensity` 不再二次乘入；
- `demand_scale` 的确定性二分标定器已实现，但正式数值必须等第五/六阶段具备 Dijkstra 利用率评估后，仅用 train 分区求得；
- Abilene 原始日历存在公开采集间断，本阶段使用连续 `timestamp_index` 驱动仿真，使用保留的原始日历计算当地时间；
- 980×980×48,096 长表不可接受，下游必须消费因子或卫星聚合结果。

## 产物

- `configs/demand_contract.yaml` 与 JSON Schema；
- `src/mucar_demand/` 需求模块；
- `scripts/audit_demand.py`；
- `tests/test_demand.py`；
- `doc/第四阶段/demand_audit.md`, `data_dictionary.md`；
- `data/manifests/stage4_demand_manifest.json`。
