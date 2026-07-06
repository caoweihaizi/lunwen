# MUCAR 数据来源与处理报告

## 1. 数据源冻结结果

### Abilene 动态流量矩阵

- 来源：SNDlib Abilene dynamic traffic；
- 版本/格式：SNDlib native ASCII TGZ；
- 时间：2004-03-01 至 2004-09-10，5 分钟粒度，官方声明存在采集间断；
- 用途：提供全局业务强度和 OD 相对变化，不映射为卫星节点；
- 引用：SNDlib 1.0，Orlowski et al. (2007)；
- 许可状态：SNDlib 页面要求发表时引用，但未在下载页给出标准 SPDX 数据许可，因此标记为 `REQUIRES_CONFIRMATION`；正式公开再分发原始文件前需人工确认。

全量审计发现 48,096 个唯一矩阵、12 个稳定节点和 132 个稠密有向 OD。压缩包成员存在 390 次时间逆序，标准化阶段按 `META time` 排序。单矩阵显式记录最少 86 个 OD；缺失 OD 按 SNDlib README 的“零需求被移除”规则补 0。

### WorldPop 人口计数

- 产品：Global2 Population Counts，R2025A v1；
- 年份/分辨率：2025，全球约 1 km（30 arc-second）约束人口计数 GeoTIFF；
- DOI：10.5258/SOTON/WP00845；
- 用途：构造地面区域人口权重；
- 许可：配置按 WorldPop 开放数据的 CC BY 4.0 记录，正式发布前仍应将下载资产随附声明归档。

栅格采用窗口化读取。NoData、负数和非有限像元不进入人口总量；有效人口按 5°×5°格网求和，人口计数聚合使用求和而非均值。

全量文件大小为 289,453,748 字节，SHA-256 为 `478d81441d39b0548c6f1a1a1d713ac7a2bf32483671c4fe0864f2d8f16cc56c`。栅格为 EPSG:4326、43,200×17,280、`float32`，NoData 为 -99,999。窗口审计得到 51,315,633 个有效像元、695,180,367 个无效/NoData 像元和 8,195,439,313.76056 的有效人口总量。

### IANA 时区边界

- 来源：Timezone Boundary Builder；
- 固定版本：2026b；
- 资产：`timezones-with-oceans-now.geojson.zip`；
- 内容：65 个带海洋覆盖的 `tzid` 要素；
- 数据许可：Open Data Commons ODbL 1.0。

区域中心经度统一为 `[-180,180)` 后执行空间相交；无匹配时使用最近边界并在审计报告中记录数量和最大距离。

最终得到 980 个非零人口 5°区域，人口权重和为 0.9999999999999984。全部区域均直接命中时区多边形，未使用最近邻回退。地面区域表 SHA-256 为 `0d3fd04f2bb4f8b8ad12c72ce7faaaffcd02745b4bc7ad555dd308e1375d89b9`。

## 2. Abilene 已完成处理结果

- 原始 SHA-256：`2f311130d77e40db88da1aa6db8055b6fce8d077bf4bae87398563e1b84e70ce`；
- 原始大小：49,203,514 字节；
- 标准化输出：`data/processed/abilene/od_timeseries.csv.gz`；
- 输出大小：103,856,957 字节；
- 输出 SHA-256：`ef66c29c72b537fa291a1df373f1b12ecf039ca57ac7800633a14a2cc753dcaa`；
- 训练段时刻数：28,857；
- 训练段总需求中位数：2,830.715213 Mbit/s。

## 3. 防泄漏与可复现规则

- 按真实时间戳排序后再执行 60%/15%/10%/15% 划分；
- `global_intensity` 只使用训练段总需求中位数；
- 原始文件只读保存并以 SHA-256 验证；
- processed 输出记录输入和处理配置哈希；
- gzip 输出固定 `mtime=0`，相同输入和配置产生相同字节序列；
- WorldPop 与时区空间处理的最终审计值由 `data/manifests/geospatial_processing_audit.json` 给出；980 个区域均具有有效 IANA 时区，人口权重误差小于 `1e-8`。

## 4. 复现命令

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python scripts/download_data.py abilene timezone_boundaries worldpop
PYTHONPATH=src .venv/bin/python scripts/inspect_raw_data.py --abilene data/raw/abilene/directed-abilene-zhang-5min-over-6months-ALL-native.tgz
PYTHONPATH=src .venv/bin/python scripts/process_data.py --abilene
PYTHONPATH=src .venv/bin/python scripts/process_geospatial.py
```
