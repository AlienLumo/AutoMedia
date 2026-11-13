# news-source · AI 资讯选题素材库

把「今天 AI 圈发生了什么」变成可直接做短视频的素材库：**资讯池聚类 → 抓原文 → 生成口播稿/事件文档 → 抓截图/录屏**。

- 输入：`1AMdata/news/pool/items.jsonl`（上游每小时轮询的资讯池）+ `config/events/<日期>.json`（当日选题）
- 输出：`1信息源/<日期>/<事件>/{原文, raw, README.md, 文案素材.md, 截图, 录屏}`
- 下游：`video-studio` 渲染成片 → 小绿工作台发布

完整用法、流程与踩坑见 **[SKILL.md](SKILL.md)**。

## 快速开始

```powershell
$py = "<项目根>/runtime/python/python.exe"
cd <项目根>/news-source/scripts

& $py cluster.py            # 1) 打印当日候选事件（只读）
# 2) 人工挑 10 个事件，写进 ../config/events/<日期>.json
& $py collect.py            # 3) 抓原文
& $py build_docs.py         # 4) 生成 README.md + 文案素材.md
& $py capture_visuals.py    # 5) 截图 / 录屏 / 人物头像
& $py stats.py              # 6) 统计核对
```

换日期：`$env:NEWS_DATE="261115"`，并准备 `config/events/261115.json`。

## 依赖

`requests`、`Pillow`、`numpy`（拼图/对比）、`patchright` + Chromium（截图录屏）、ffmpeg（拼录屏）。
运行时由项目 `runtime/` 提供；单独部署见 `requirements.txt`。

## 目录

```
scripts/   12 个脚本（news_paths.py 统一解析路径）
config/    buckets.json 分桶关键词 + events/<日期>.json 当日选题 + sources.tsv 上游源注册表（281 个源）
docs/      源库说明.md（信息源 P0–P3 分层、字段说明、平台限制）
examples/  261111/ 示例素材库（2026-11-11，仅文本与链接）
```

## 说明

- 路径全部由 `scripts/news_paths.py` 解析，可用 `AUTOMEDIA_ROOT`（项目根）/ `NEWS_DATE` / `NEWS_DATA_ROOT` / `NEWS_POOL` / `NEWS_RUNTIME` 覆盖。
- 只读抓取；付费墙拿不到就标注缺口，不编造正文。
- 素材库目录（`1信息源/`）是数据产物，不入 git —— 本仓库只放 skill 代码与配置。
