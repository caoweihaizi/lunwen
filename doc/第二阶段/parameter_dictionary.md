# 第二阶段参数字典

## 字段说明

“属性”为“原始”的字段直接来自 YAML；“派生”字段只能由原始契约计算。“依据”中的“技术大纲”和“第二阶段路线”分别指根目录的《技术大纲》与本阶段冻结文档。

## 研究契约

| 路径 | 类型 | 单位 | 冻结值 | 依据 | 属性 | 首次消费阶段 |
|---|---|---|---|---|---|---|
| `schema_version` | string | — | `1.0` | 契约版本 | 原始 | 2 |
| `study_id` | string | — | `mucar_master_thesis` | 技术大纲 | 原始 | 2 |
| `title` | string | — | 面向不完整遥测的置信度感知低轨卫星网络流量预测与韧性路由 | 技术大纲 | 原始 | 2 |
| `research_questions[0].id/text` | object | — | `RQ1` / 路由状态、缺失掩码、信息年龄与动态拓扑的预测及跨策略泛化 | 技术大纲 RQ1 | 原始 | 9 |
| `research_questions[1].id/text` | object | — | `RQ2` / 因果、延迟标签感知区间的 90% 覆盖 | 技术大纲 RQ2 | 原始 | 11 |
| `research_questions[2].id/text` | object | — | `RQ3` / 区间、新鲜度与拥塞风险驱动的尾延迟与丢包改善 | 技术大纲 RQ3 | 原始 | 13 |
| `claim_boundaries.new_foundational_learning_theory` | boolean | — | `false` | 创新边界 | 原始 | 16 |
| `claim_boundaries.unconditional_conformal_coverage_under_mar` | boolean | — | `false` | MAR 选择偏差边界 | 原始 | 11 |
| `claim_boundaries.generalize_to_commercial_constellations` | boolean | — | `false` | 理想 Walker 星座边界 | 原始 | 16 |
| `claim_boundaries.generalize_to_onboard_hardware` | boolean | — | `false` | 仅 Python/M4 Pro 仿真 | 原始 | 16 |
| `data.source_manifest_ids` | string[] | — | `abilene, worldpop, timezone_boundaries, ground_regions` | 第一阶段 manifest | 原始 | 4 |
| `data.total_traffic_slots` | integer | slot | `48096` | Abilene 全量审计 | 原始 | 4 |
| `data.splits.train.start/stop/count` | integer | slot | `0/28857/28857` | 第一阶段时间分区 | 原始 | 4 |
| `data.splits.validation.start/stop/count` | integer | slot | `28857/36071/7214` | 第一阶段时间分区 | 原始 | 4 |
| `data.splits.calibration.start/stop/count` | integer | slot | `36071/40880/4809` | 第一阶段时间分区 | 原始 | 4 |
| `data.splits.test.start/stop/count` | integer | slot | `40880/48096/7216` | 第一阶段时间分区 | 原始 | 4 |
| `data.window_crosses_split_boundary` | boolean | — | `false` | 防泄漏契约 | 原始 | 9 |
| `data.fit_scalers_on` | string | — | `train` | 防泄漏契约 | 原始 | 4 |
| `data.tune_hyperparameters_on` | string[] | — | `train, validation` | 防泄漏契约 | 原始 | 9 |
| `data.conformal_initialization_on` | string | — | `calibration` | 防泄漏契约 | 原始 | 11 |
| `data.final_evaluation_on` | string | — | `test` | 防泄漏契约 | 原始 | 14 |
| `success_targets.target_interval_coverage` | number | ratio | `0.90` | RQ2 | 原始 | 11 |
| `success_targets.accepted_coverage_min/max` | number | ratio | `0.87/0.93` | 90% 目标的验收带 | 原始 | 11 |
| `success_targets.quantile_crossing_rate` | number | ratio | `0.0` | 分位数单调性 | 原始 | 10 |
| `success_targets.formal_seed_count` | integer | seed | `5` | 统一工程规范 | 原始 | 14 |

## 仿真契约

| 路径 | 类型 | 单位 | 冻结值 | 依据 | 属性 | 首次消费阶段 |
|---|---|---|---|---|---|---|
| `schema_version` | string | — | `1.0` | 契约版本 | 原始 | 2 |
| `time.epoch_utc` | datetime string | UTC | `2025-01-01T00:00:00Z` | 固定仿真历元 | 原始 | 3 |
| `time.traffic_interval_s` | integer | s | `300` | Abilene 5 min | 原始 | 4 |
| `time.service_step_s` | integer | s | `1` | 队列服务粒度 | 原始 | 5 |
| `time.routing_step_s` | integer | s | `1` | 逐步路由决策 | 原始 | 5 |
| `time.orbit_update_s` | integer | s | `10` | 拓扑更新粒度 | 原始 | 3 |
| `time.telemetry_step_s` | integer | s | `1` | 完整真值采样 | 原始 | 5 |
| `time.prediction_refresh_s` | integer | s | `300` | 预测样本粒度 | 原始 | 9 |
| `time.prediction_horizons` | integer[] | traffic slot | `[1,3]` | 5/15 min 时域 | 原始 | 9 |
| `units.time/distance/speed` | string | — | `s/km/km/s` | 内部单位契约 | 原始 | 3 |
| `units.rate/volume/delay/configured_angle` | string | — | `Mbit/s, Mbit, s, degree` | 内部单位契约 | 原始 | 3 |
| `orbit.constellation_type` | string | — | `walker_star` | 技术大纲 | 原始 | 3 |
| `orbit.total_satellites/planes/satellites_per_plane` | integer | satellite/plane | `66/6/11` | Walker Star 66/6/2 | 原始 | 3 |
| `orbit.phasing` | integer | — | `2` | Walker Star 66/6/2 | 原始 | 3 |
| `orbit.altitude_km` | number | km | `780.0` | 第二阶段路线 | 原始 | 3 |
| `orbit.inclination_deg` | number | degree | `86.4` | 第二阶段路线 | 原始 | 3 |
| `orbit.eccentricity` | number | — | `0.0` | 圆轨道简化 | 原始 | 3 |
| `orbit.raan_span_deg/raan_spacing_deg` | number | degree | `180.0/30.0` | Walker Star 平面分布 | 原始 | 3 |
| `orbit.propagator` | string | — | `analytic_two_body_circular` | 理想轨道边界 | 原始 | 3 |
| `earth.model` | string | — | `spherical` | 第一版简化 | 原始 | 3 |
| `earth.radius_km` | number | km | `6378.137` | WGS84 赤道半径 | 原始 | 3 |
| `earth.mu_km3_s2` | number | km³/s² | `398600.4418` | 地球标准引力参数 | 原始 | 3 |
| `earth.rotation_rad_s` | number | rad/s | `7.2921159e-5` | 地球自转角速度 | 原始 | 3 |
| `earth.light_speed_km_s` | number | km/s | `299792.458` | 真空光速 | 原始 | 3 |
| `isl.storage` | string | — | `directed_edges` | 有向服务量建模 | 原始 | 3 |
| `isl.intra_plane_neighbors/inter_plane_neighbors_max` | integer | edge/node | `2/2` | 四邻居上限 | 原始 | 3 |
| `isl.connect_star_seam` | boolean | — | `false` | Walker Star 接缝关闭 | 原始 | 3 |
| `isl.inter_plane_pairing` | string | — | `mutual_nearest_then_sat_id` | 确定性一一匹配 | 原始 | 3 |
| `isl.crosslink_max_abs_lat_deg` | number | degree | `70.0` | 高纬跨轨链关闭 | 原始 | 3 |
| `isl.require_earth_clearance` | boolean | — | `true` | 地球遮挡约束 | 原始 | 3 |
| `isl.max_distance_km` | number | km | `5000.0` | ISL 最大距离 | 原始 | 3 |
| `link.capacity_mbps` | number | Mbit/s | `1000.0` | 统一链路容量 | 原始 | 5 |
| `link.buffer_delay_budget_s` | number | s | `0.5` | 缓存时延预算 | 原始 | 5 |
| `link.max_wait_s` | number | s | `5.0` | 最大等待规则 | 原始 | 5 |
| `link.queue_discipline` | string | — | `fifo_fluid_volume` | 流量体积近似 | 原始 | 5 |
| `link.update_order` | string | — | `arrivals_overflow_service` | 固定队列更新顺序 | 原始 | 5 |
| `link.failed_link_service_mbit` | number | Mbit | `0.0` | 故障边无服务 | 原始 | 5 |
| `coverage.ground_region_source` | path string | — | `data/processed/geospatial/ground_regions.csv` | 第一阶段产物 | 原始 | 3 |
| `coverage.ground_altitude_km` | number | km | `0.0` | 地面静止点假设 | 原始 | 3 |
| `coverage.minimum_elevation_deg` | number | degree | `10.0` | 覆盖门限 | 原始 | 3 |
| `coverage.selection` | string | — | `maximum_elevation_then_sat_id` | 确定性接入规则 | 原始 | 3 |
| `coverage.uncovered_behavior` | string | — | `access_backlog` | 无覆盖不静默丢弃 | 原始 | 4 |
| `coverage.refresh_s` | integer | s | `10` | 与轨道更新同步 | 原始 | 3 |
| `demand_calibration.allowed_split/behavior_policy/scenario` | string | — | `train/dijkstra/normal_complete_no_failure` | 防泄漏标定规则 | 原始 | 4 |
| `demand_calibration.statistic` | string | — | `p90_active_link_mean_utilization_per_traffic_interval` | 训练段利用率标定 | 原始 | 4 |
| `demand_calibration.target/accepted_min/accepted_max` | number | ratio | `0.60/0.55/0.65` | 负载工作区间 | 原始 | 4 |
| `demand_calibration.search_min/search_max` | number | scale | `0.001/1000.0` | 确定性二分搜索边界 | 原始 | 4 |
| `demand_calibration.max_iterations/relative_tolerance` | number | iteration/ratio | `30/0.01` | 二分搜索停止条件 | 原始 | 4 |
| `seeds.development` | integer | seed | `202500` | 开发调试 | 原始 | 3 |
| `seeds.formal` | integer[] | seed | `202501–202505` | 5 个正式种子 | 原始 | 3 |
| `seeds.derivation` | string | — | `numpy_seedsequence` | 稳定派生算法 | 原始 | 3 |
| `seeds.key_order` | string[] | — | `master_seed,scenario_id,policy_id,module_id,replicate_id` | 随机流隔离 | 原始 | 3 |
| `seeds.module_ids.demand/burst/failure/missing` | integer | id | `1/2/3/4` | 随机模块枚举 | 原始 | 4/7 |
| `seeds.module_ids.behavior_policy/model_init/rl_env` | integer | id | `5/6/7` | 随机模块枚举 | 原始 | 6/9/12 |

## 派生量

| 路径 | 类型 | 单位 | 算法/当前值 | 依据 | 属性 | 首次消费阶段 |
|---|---|---|---|---|---|---|
| `orbit_radius_km` | number | km | `earth.radius_km + orbit.altitude_km = 7158.137` | 二体轨道 | 派生 | 3 |
| `mean_motion_rad_s` | number | rad/s | `sqrt(mu/r³) = 0.001042482753` | 二体圆轨道 | 派生 | 3 |
| `orbit_period_s` | number | s | `2π/n = 6027.135978` | 二体圆轨道 | 派生 | 3 |
| `raan_deg` | number[] | degree | `[0,30,60,90,120,150]` | `p×raan_spacing_deg` | 派生 | 3 |
| `phase_deg` | number[66] | degree | `(s×360/11 + p×360×2/66) mod 360` | Walker 相位规则 | 派生 | 3 |
| `service_capacity_mbit` | number | Mbit | `capacity_mbps×service_step_s = 1000` | 链路服务 | 派生 | 5 |
| `buffer_capacity_mbit` | number | Mbit | `capacity_mbps×buffer_delay_budget_s = 500` | 缓存预算 | 派生 | 5 |
| `service_steps_per_traffic_interval` | integer | step | `300/1 = 300` | 双层时间轴 | 派生 | 4 |
| `orbit_updates_per_traffic_interval` | integer | update | `300/10 = 30` | 双层时间轴 | 派生 | 3 |
| `derived_seed` | uint32 | seed | `SeedSequence([master,scenario,policy,module,replicate])` | 随机性契约 | 派生 | 3 |
