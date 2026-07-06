# 第四阶段数据字典

## 时间总量

| 字段 | 类型 | 单位 | 约束 | 用途 |
|---|---|---|---|---|
| `timestamp_index` | int | 5 min slot | `0..48095` 连续 | 分区、轨道时间和场景索引 |
| `source_timestamp` | string | UTC calendar | `YYYYMMDD-HHMM`，允许官方采集间断 | 仅作 Abilene 溯源 |
| `simulation_timestamp_utc` | datetime | UTC | `epoch_utc + timestamp_index×300s` | 当地活动、轨道与接入的唯一时间轴 |
| `total_demand_mbps` | float | Mbit/s | 非负、有限，slot 内 132 行一致 | 基础 OD 总量 |
| `global_intensity` | float | ratio | 非负、有限 | 预测特征，不二次缩放总量 |

## 地面区域

| 字段 | 类型 | 单位 | 约束 | 用途 |
|---|---|---|---|---|
| `region_id` | string | — | 980 个唯一 ID | OD 维度与追溯键 |
| `centroid_lat/lon` | float | degree | lat `[-90,90]`, lon `[-180,180)` | 卫星接入 |
| `population` | float | person | 非负、有限 | 热点抽样依据 |
| `timezone` | string | IANA zone | `zoneinfo` 可解析 | 当地时间 |
| `population_weight` | float | ratio | 非负，总和误差 `<1e-8` | 基础空间权重 |
| `activity_multiplier` | float | ratio | `[0.35,1.0]` | 日周活跃度 |
| `spatial_weight` | float | ratio | 非负，每 slot 归一 | OD 起点/终点权重 |

## 因子化 OD

| 字段 | 类型 | 单位 | 约束 |
|---|---|---|---|
| `region_ids` | tuple[string] | — | 唯一、固定排序 |
| `coefficient_mbps` | float | Mbit/s | `total/Z` |
| `origin_factors` | float64[N] | ratio | 基础时归一，干预后允许放大 |
| `destination_factors` | float64[N] | ratio | 归一 |
| `flow(i,j)` | float | Mbit/s | `i==j` 时为 0，其他为 `coefficient*o_i*d_j` |
| `base_total_mbps` | float | Mbit/s | 干预前总量 |
| `scenario_total_mbps` | float | Mbit/s | 干预后总量 |

## 接入聚合

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `satellite_pairs_mbps` | map[(src_sat,dst_sat),float] | Mbit/s | 需进入 ISL 的卫星对需求 |
| `satellite_od_mbps` | float | Mbit/s | 卫星对需求合计 |
| `local_delivery_mbps` | float | Mbit/s | 起终区域接入同星的本地交付 |
| `access_backlog_mbps` | float | Mbit/s | 任一端无覆盖的需求 |

`satellite_od_mbps + local_delivery_mbps + access_backlog_mbps` 必须等于 `scenario_total_mbps`。
