# MUCAR 数据字典

## Abilene 标准化长表

文件：`data/processed/abilene/od_timeseries.csv.gz`

| 字段 | 类型 | 单位 | 允许缺失 | 说明与下游用途 |
|---|---|---|---|---|
| `timestamp_index` | int | 5 分钟时隙 | 否 | 按真实时间戳排序后的连续索引；用于时间划分和滑动窗口 |
| `timestamp` | string | `YYYYMMDD-HHMM` | 否 | SNDlib 原始时间；保留官方采集缺口 |
| `src_id` | string | — | 否 | Abilene 原始源节点；只用于提取时间/OD变化模式 |
| `dst_id` | string | — | 否 | Abilene 原始目的节点；`src_id != dst_id` |
| `demand_raw` | float | Mbit/s | 否 | 原始需求；被 SNDlib 省略的零需求显式补 0 |
| `total_demand` | float | Mbit/s | 否 | 同一时刻 132 个 OD 需求之和 |
| `global_intensity` | float | 比值 | 否 | `total_demand / 训练段总需求中位数` |
| `od_share` | float | 比例 | 否 | OD 占当时刻总需求比例；总需求为零时取 0 |

时间划分按排序后矩阵数执行：60%/15%/10%/15%，训练段为前 28,857 个时刻。任何标准化统计量只能来自训练段。

## 地面区域表

文件：`data/processed/geospatial/ground_regions.csv`

| 字段 | 类型 | 单位 | 允许缺失 | 说明与下游用途 |
|---|---|---|---|---|
| `region_id` | string | — | 否 | 固定 5°×5°格网区域标识 |
| `centroid_lat` | float | 度 | 否 | 区域中心纬度 |
| `centroid_lon` | float | 度 | 否 | `[-180,180)` 内的区域中心经度 |
| `population` | float | 人 | 否 | 区域内有效 WorldPop 人口计数之和 |
| `timezone` | string | IANA tzid | 否 | 本地昼夜周期使用的时区 |
| `population_weight` | float | 比例 | 否 | 区域人口/全球有效人口；总和误差必须小于 `1e-8` |
| `timezone_match` | enum | — | 否 | `intersects` 或边界外回退的 `nearest` |

## Manifest 通用字段

| 字段 | 说明 |
|---|---|
| `dataset_id`, `role` | 数据标识与研究用途 |
| `source_page`, `requested_url`, `final_url` | 来源和下载追踪 |
| `retrieved_at_utc`, `release_version` | 获取时间与固定版本 |
| `license`, `citation` | 许可与引用信息 |
| `filename`, `byte_size`, `sha256` | 本地资产及完整性 |
| `processing_config_sha256` | 规范化处理配置哈希 |
| `generated_outputs` | 由该输入产生的文件 |
