# 第一步运行环境报告

## 硬件与系统

- 系统：macOS 26.2，Apple arm64；
- Python：3.9.6；
- 执行开始时磁盘总量：494,384,795,648 字节；
- 执行开始时可用磁盘：289,042,341,888 字节。

## Python 环境

项目使用本地 `.venv`，依赖固定于 `requirements.txt`：

- PyYAML 6.0.3；
- NumPy 2.0.2；
- rasterio 1.4.3；
- Shapely 2.0.7；
- pyogrio 0.10.0；
- PyArrow 17.0.0。

由于当前网络到官方 PyPI wheel CDN 的连接连续两次在下载 rasterio 时重置，实际安装使用阿里云 PyPI 镜像，但版本锁和 wheel 平台未改变。

## 数据端点检查

- SNDlib Abilene：可访问并已完成下载、哈希和全量解析；
- Timezone Boundary Builder 2026b：可访问并已完成下载、哈希和 GeoJSON 结构检查；
- WorldPop R2025A：可访问，响应声明 289,453,748 字节、EPSG:4326 GeoTIFF；服务器单连接限速且实际忽略 Range 请求，采用命名后台会话完成单连接原子下载。

## 已知执行约束

- SNDlib TGZ 内部文件顺序不是时间顺序，必须按 `META time` 排序；
- WorldPop 下载端点不支持实际可用的断点分块，下载过程不可并行拼块；
- `.venv`、原始数据、中间数据和完整 processed 数据不进入 Git；配置、测试、清单和报告进入 Git。
