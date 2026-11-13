# CHANGELOG

## 0.1.0 — 2026-11-13

- 收编 `1信息源/_tools/` 的 12 个脚本为统一 skill：`scripts/` 主流程 + `scripts/_dev/` 一次性调试脚本。
- 路径全部收敛到 `scripts/news_paths.py`（项目根 / 素材根 / 日期 / 资讯池 / 运行时），支持
  `NEWS_DATE`、`NEWS_DATA_ROOT`、`NEWS_POOL`、`NEWS_RUNTIME` 环境变量覆盖；去掉脚本里的绝对路径。
- 配置外置：`config/buckets.json`（事件分桶关键词）、`config/events/<日期>.json`（当日选题与链接）。
- `collect_261111.py` → `collect.py`，事件清单从配置文件读取，新增 `--date` / `--events` 参数；
  默认行为与原脚本一致（默认 261111）。
- `cluster_today.py` → `cluster.py`，分桶改读 `config/buckets.json`。
- `stats_events.py` → `stats.py`；`make_dpi_compare.py` / `test_dpi_wayback.py` 归入 `scripts/_dev/`。
- 文档：新增 `SKILL.md`（流程/配置/踩坑/边界）、`README.md`、`requirements.txt`。
- 素材库 `1信息源/` 不再入库（图片/录屏/原文属于数据产物），仓库只保留代码与配置。
