# 第四阶段：OD 需求生成器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` and `superpowers:test-driven-development`. Execute tasks in order and do not implement queues or routing.

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-06
- Verification Status: UNVERIFIED
- Version Label: stage4_plan_v1

**Goal:** 将 Abilene 全局时间强度、人口与当地时间转换为可精确守恒的地面区域 OD，并在接入映射前施加局部突发、持续热点与缓慢漂移。

**Architecture:** 时间总量、区域权重和干预为独立纯函数。OD 矩阵用“总量 + 起点权重 + 终点权重 + 非自环归一化常数”精确因子化，只在测试或小规模输出时展开。接入映射复用第三阶段覆盖 API。

**Tech Stack:** Python 3.9, NumPy, zoneinfo, csv/gzip/json/hashlib, PyYAML, jsonschema, unittest.

---

## 1. 阶段边界

### 纳入

- 从 `od_timeseries.csv.gz` 每个时隔读取唯一 `timestamp,total_demand,global_intensity`；
- 人口权重、IANA 时区和确定性当地日周活跃度；
- 排除 `src_region == dst_region` 的精确因子化 OD；
- `normal`, `local_burst`, `persistent_hotspot`, `slow_drift` 四种需求场景；
- 干预后的需求先于卫星接入映射；
- 空间权重、总量守恒、干预顺序、分区和复现审计。

### 不纳入

- 不实现队列、链路服务、Dijkstra/ECMP 或故障注入；
- 不把 Abilene 12 个路由器映射为卫星或地面城市；
- 不物化 980×980×48,096 的全量长表；
- 不在测试、验证、校准或测试分区标定 `demand_scale`。

## 2. 冻结的生成规则

### 2.1 时间总量

`total_demand` 的单位为 Mbit/s，作为未缩放的基础 OD 总量。`global_intensity` 仅用作可追溯特征，不再乘回总量。Abilene 原始日历仅保留为 `source_timestamp`；当地活动、轨道和接入统一使用 `simulation_datetime = epoch_utc + timestamp_index * traffic_interval_s`。第二阶段的 `demand_scale` 保持独立参数：本阶段提供标定接口，实际数值必须在第五/六阶段具备 Dijkstra 和链路利用率后仅用 train 分区求得。

### 2.2 当地日周活跃度

```text
local_hour = hour + minute/60
activity = 0.35 + 0.65 * (0.5 + 0.5*cos(2π*(local_hour-14)/24))
raw_region_weight = population_weight * activity
region_weight = raw_region_weight / sum(raw_region_weight)
```

活跃度在当地 14:00 达到 1.0，02:00 达到 0.35。起点与终点使用同一归一化权重。

### 2.3 非自环因子化 OD

对归一化起点权重 `o_i` 和终点权重 `d_j`：

```text
Z = 1 - sum_i(o_i*d_i)
D_ij = total_demand_mbps * o_i*d_j/Z, i != j
D_ii = 0
```

`Z` 必须严格大于 0。任意展开或按卫星聚合后的总量误差必须小于 `max(1e-9, total*1e-12)`。

### 2.4 场景干预

| 场景 | 地区数 | 倍率 | 持续时间 | 规则 |
|---|---:|---:|---:|---|
| `normal` | 0 | 1.0 | 全程 | 不改变权重 |
| `local_burst` | 5 | 4.0 | 12 slots / 1 h | 放大以热点为起点的需求 |
| `persistent_hotspot` | 5 | 2.0 | 288 slots / 24 h | 放大以热点为起点的需求 |
| `slow_drift` | 10 | 1.0→1.5 | 2016 slots / 7 d | 起点倍率线性增长 |

热点由 `derive_seed(master_seed, scenario_id, 0, "burst", 0, seeds)` 创建 RNG，按 `population_weight` 无放回抽样，选中后按 `region_id` 排序并写入 manifest。干预通过修改起点权重改变总量，不重新归一化；因此场景总量等于干预后矩阵求和，并必须同时保留 `base_total_mbps` 和 `scenario_total_mbps`。

### 2.5 接入顺序

```text
Abilene total -> local-time spatial weights -> base factorized OD
-> demand intervention -> ground-region access assignment
-> satellite-pair aggregation
```

backlog 区域的需求进入 `access_backlog_mbps`，不映射到卫星对，且满足：

```text
scenario_total_mbps = mapped_satellite_od_mbps + access_backlog_mbps
```

## 3. 配置与文件

```text
configs/demand_contract.yaml
configs/schemas/demand_contract.schema.json
src/mucar_demand/
  __init__.py
  config.py          # 严格加载 demand contract
  temporal.py        # Abilene 时隔汇总读取
  spatial.py         # 时区活跃度和区域权重
  factorized.py      # 精确非自环因子化 OD
  interventions.py  # 场景、热点与倍率
  access.py          # 干预后接入与卫星对聚合
  audit.py           # 守恒、分区、复现审计
scripts/audit_demand.py
tests/test_demand.py
doc/第四阶段/
  第四阶段-OD需求生成器.md
  demand_audit.md
  data_dictionary.md
  stage4_completion_audit.md
data/manifests/stage4_demand_manifest.json
```

## 4. 固定 API

| API | 返回/作用 |
|---|---|
| `load_demand_contract(path)` | 严格不可变需求配置 |
| `iter_temporal_slots(path)` | 按 `timestamp_index` 产生唯一时间总量 |
| `load_demand_regions(path)` | 读取人口、时区和权重 |
| `spatial_weights(regions, timestamp_utc, contract)` | 归一化空间权重 |
| `FactorizedOD.from_weights(total, ids, origin, destination)` | 非自环因子化 OD |
| `FactorizedOD.flow(src,dst)` | 单个地面 OD 速率 |
| `FactorizedOD.materialize()` | 仅用于单时隔审计的稠密矩阵 |
| `choose_hotspots(...)` | 固定种子的人口加权无放回抽样 |
| `apply_intervention(base_od, scenario, relative_slot)` | 返回干预后 OD 及元数据 |
| `aggregate_to_satellites(od, assignments)` | 返回卫星对矩阵与 backlog |
| `audit_demand_pipeline(...)` | 返回可 JSON 序列化审计 |

## 5. TDD 任务

### Task 1：配置与时间读取

- [ ] 先测试 demand contract 未知/缺失字段报错。
- [ ] 测试 Abilene 同一 slot 的 132 行必须共享 timestamp、total 和 intensity；不一致即报错。
- [ ] 测试 48,096 个 `timestamp_index` 严格连续；原始日历时间必须严格递增并保留 SNDlib 已公开的采集间断，不伪造缺失时刻。
- [ ] 实现 `configs/demand_contract.yaml` 及 Schema，`additionalProperties=false`。

### Task 2：人口—时区权重

- [ ] 先测试活跃度在 14:00 为 1.0、02:00 为 0.35。
- [ ] 使用两个不同 IANA 时区的人工区域测试同 UTC 时刻的权重不同。
- [ ] 对每个时隔验证权重非负、有限且总和误差 `<1e-12`。

### Task 3：因子化 OD 与守恒

- [ ] 先用 3 区域手工计算非自环 OD，断言对角线为 0、所有非对角线非负且总和等于 total。
- [ ] 测试权重不归一、负值、NaN、ID 重复和 `Z<=0` 报错。
- [ ] 实现不物化的 `flow`, `row_totals`, `total_mbps` 和审计用 `materialize`。

### Task 4：干预

- [ ] 先测试 4× burst 仅放大选中起点的行，基础 OD 不被就地修改。
- [ ] 测试干预前后总量的解析关系、持续边界和 drift 线性倍率。
- [ ] 使用相同种子两次选取热点，必须完全一致；不同场景种子流必须分离。

### Task 5：接入聚合

- [ ] 先用 3 区域/2 卫星人工映射测试卫星对聚合。
- [ ] 测试自卫星对可保留为本地交付量，不进入 ISL，但仍纳入守恒。
- [ ] 测试 backlog 区域相关的起点或终点需求全部进入 `access_backlog_mbps`。
- [ ] 断言 `satellite_od + local_delivery + backlog == scenario_total`。

### Task 6：审计与文档

- [ ] 在 train/validation/calibration/test 每个分区取首、中、末三个 slot，审计四场景的权重与总量。
- [ ] 正式运行加载 48,096 个时间总量和 980 区域，不展开全量 OD。
- [ ] 输出 `demand_audit.md`, `data_dictionary.md`, `stage4_completion_audit.md` 和 stage4 manifest。
- [ ] 两次运行以及不同 `PYTHONHASHSEED` 的规范化哈希必须一致。

## 6. 验收命令

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_contracts.py
PYTHONPATH=src .venv/bin/python scripts/audit_constellation.py
PYTHONPATH=src .venv/bin/python scripts/audit_demand.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests
git diff --check
```

## 7. 完成门槛

- [x] 48,096 个 Abilene 时间总量唯一、索引连续、非负且有限；
- [x] 980 区域人口—当地时间权重非负且归一；
- [x] 基础非自环 OD 的全局总量误差在容差内；
- [x] 四类场景的干预仅发生在接入映射前；
- [x] 卫星对、本地交付和 backlog 聚合严格守恒；
- [x] 热点和审计哈希可复现；
- [x] 不物化全量 980×980×48,096 OD；
- [x] 第一至第四阶段全量测试通过。

## 8. 失败分支

| 失败 | 强制处理 |
|---|---|
| Abilene `timestamp_index` 重复/断裂或 slot 内总量不一致 | 回第一阶段，不进入空间分配；原始日历采集间断仅记录不补齐 |
| 人口或活跃度权重无法归一 | 停止，不回退为均匀权重 |
| 基础 OD 不守恒 | 回 Task 3 检查非自环归一化 `Z` |
| 干预后基础 OD 被修改 | 判定为数据污染，重建该场景 |
| 需求先映射再突发 | 判定干预顺序失败，该轮产物作废 |
| 资源不足 | 保留因子化表示并分块聚合，不删减区域或时间段 |
